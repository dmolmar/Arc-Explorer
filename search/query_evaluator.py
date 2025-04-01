import sqlite3
from typing import Set, TYPE_CHECKING

# Import utility function
from utils.path_utils import normalize_path

# Import AST node types from the parser module
from .query_parser import ASTNode, TagNode, AndNode, OrNode, NotNode, BracketNode, AllImagesNode

# Use TYPE_CHECKING to avoid circular import issues with Database
if TYPE_CHECKING:
    from database.db_manager import Database

class SearchQueryEvaluator:
    """
    Evaluates an AST generated by SearchQueryParser against the database
    to retrieve a set of matching image IDs.
    """
    def __init__(self, db: 'Database', selected_directories: Set[str]):
        """
        Initializes the evaluator.

        Args:
            db: An instance of the Database manager.
            selected_directories: A set of normalized directory paths currently active.
                                   Used to scope the search (especially for NOT queries).
        """
        self.db = db
        # Store normalized selected directories
        self.selected_directories = {normalize_path(d) for d in selected_directories}

    def evaluate(self, node: ASTNode) -> Set[str]:
        """
        Recursively evaluates the AST node and returns a set of matching image IDs.

        Args:
            node: The current AST node to evaluate.

        Returns:
            A set of image IDs matching the query represented by the node.
        """
        result: Set[str] = set()

        if isinstance(node, TagNode):
            # get_image_ids_by_tag now filters by directory scope internally
            result = self.get_image_ids_by_tag(node.tag)

        elif isinstance(node, AllImagesNode):
            # Returns all images within the selected directories scope
            result = self.get_all_image_ids_in_scope()

        elif isinstance(node, AndNode):
            left_set = self.evaluate(node.left)
            # Optimization: If left set is empty, intersection will be empty
            if not left_set:
                result = set()
            else:
                right_set = self.evaluate(node.right)
                result = left_set.intersection(right_set)

        elif isinstance(node, OrNode):
            left_set = self.evaluate(node.left)
            right_set = self.evaluate(node.right)
            result = left_set.union(right_set)

        elif isinstance(node, NotNode):
            # Get all images within the current scope (selected directories)
            all_in_scope = self.get_all_image_ids_in_scope()
            # Evaluate the node to be excluded
            excluded_set = self.evaluate(node.node)
            # Result is all images in scope minus the excluded ones
            result = all_in_scope - excluded_set

        elif isinstance(node, BracketNode):
            # Brackets primarily affect parsing order, evaluation just processes the inner expression
            result = self.evaluate(node.expression)

        else:
            raise ValueError(f"Unknown AST node type during evaluation: {type(node)}")

        return result

    def get_image_ids_by_tag(self, tag: str) -> Set[str]:
        """
        Retrieves image IDs associated with a specific tag from the database,
        filtered by the currently selected directories.
        """
        # If no directories are selected, no images can match the scope.
        if not self.selected_directories:
            return set()

        try:
            with self.db.lock: # Use the database's lock
                with sqlite3.connect(self.db.db_path) as conn:
                    conn.execute("PRAGMA query_only = ON")
                    cursor = conn.cursor()

                    # Build directory conditions
                    dir_conditions = []
                    dir_params = []
                    for norm_dir in self.selected_directories:
                         if not norm_dir.endswith('/'): norm_dir += '/'
                         dir_conditions.append("i.path LIKE ?")
                         dir_params.append(f"{norm_dir}%")
                    dir_where_clause = " OR ".join(dir_conditions)

                    # Combine tag and directory conditions
                    # Case-insensitive tag search: lower(t.name) = lower(?)
                    query = f"""
                        SELECT it.image_id
                        FROM image_tags it
                        JOIN tags t ON it.tag_id = t.id
                        JOIN images i ON it.image_id = i.id
                        WHERE lower(t.name) = lower(?) AND ({dir_where_clause})
                    """
                    final_params = [tag] + dir_params

                    cursor.execute(query, final_params)
                    result = {row[0] for row in cursor.fetchall()}
            return result
        except sqlite3.Error as e:
            print(f"Database error getting images by tag '{tag}' within scope: {e}")
            return set()

    def get_all_image_ids_in_scope(self) -> Set[str]:
        """Retrieves all image IDs within the currently selected directories."""
        if not self.selected_directories:
            return set()

        try:
            with self.db.lock:
                with sqlite3.connect(self.db.db_path) as conn:
                    conn.execute("PRAGMA query_only = ON")
                    cursor = conn.cursor()
                    # Build WHERE clause for directories
                    dir_conditions = []
                    params = []
                    for norm_dir in self.selected_directories:
                         if not norm_dir.endswith('/'): norm_dir += '/'
                         dir_conditions.append("path LIKE ?")
                         params.append(f"{norm_dir}%")

                    where_clause = " OR ".join(dir_conditions)
                    query = f"SELECT id FROM images WHERE {where_clause}"

                    cursor.execute(query, params)
                    result = {row[0] for row in cursor.fetchall()}
            return result
        except sqlite3.Error as e:
            print(f"Database error getting all image IDs in scope: {e}")
            return set()

    def filter_by_directory_scope(self, image_ids: Set[str]) -> Set[str]:
         """Filters a given set of image IDs, keeping only those within the selected directories."""
         # This might be inefficient if called repeatedly. Consider integrating into initial queries.
         # However, it ensures results from TagNode etc. are correctly scoped.
         if not self.selected_directories or not image_ids:
             return image_ids # No filtering needed or possible

         try:
             with self.db.lock:
                 with sqlite3.connect(self.db.db_path) as conn:
                     conn.execute("PRAGMA query_only = ON")
                     cursor = conn.cursor()

                     # Build WHERE clause for directories
                     dir_conditions = []
                     params = []
                     for norm_dir in self.selected_directories:
                          if not norm_dir.endswith('/'): norm_dir += '/'
                          dir_conditions.append("path LIKE ?")
                          params.append(f"{norm_dir}%")
                     dir_where_clause = " OR ".join(dir_conditions)

                     # Query images matching the IDs AND the directory scope
                     id_placeholders = ','.join('?' for _ in image_ids)
                     query = f"SELECT id FROM images WHERE id IN ({id_placeholders}) AND ({dir_where_clause})"
                     final_params = list(image_ids) + params

                     cursor.execute(query, final_params)
                     filtered_ids = {row[0] for row in cursor.fetchall()}
             return filtered_ids
         except sqlite3.Error as e:
             print(f"Database error filtering by directory scope: {e}")
             return set() # Return empty set on error