import unittest
from fastapi.testclient import TestClient
from main import app  # Assuming the FastAPI app is instantiated in main.py

class TestAPIRoutes(unittest.TestCase):
    """
    Integration tests for the API routes to ensure correct HTTP responses and error handling.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up the TestClient for the FastAPI app.
        """
        cls.client = TestClient(app)

    def test_root_endpoint(self):
        """
        Test the root endpoint to ensure it returns a successful response.
        """
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.json())

    def test_non_existent_endpoint(self):
        """
        Test a non-existent endpoint to ensure it returns a 404 error.
        """
        response = self.client.get("/non-existent")
        self.assertEqual(response.status_code, 404)

    def test_create_item(self):
        """
        Test the item creation endpoint to ensure it returns a successful response.
        """
        response = self.client.post("/items/", json={"name": "Test Item", "description": "A test item."})
        self.assertEqual(response.status_code, 201)
        self.assertIn("id", response.json())

    def test_get_item(self):
        """
        Test the item retrieval endpoint to ensure it returns the correct item.
        """
        # First, create an item
        create_response = self.client.post("/items/", json={"name": "Test Item", "description": "A test item."})
        item_id = create_response.json().get("id")

        # Now, retrieve the item
        get_response = self.client.get(f"/items/{item_id}")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json().get("name"), "Test Item")

    def test_update_item(self):
        """
        Test the item update endpoint to ensure it updates the item correctly.
        """
        # First, create an item
        create_response = self.client.post("/items/", json={"name": "Test Item", "description": "A test item."})
        item_id = create_response.json().get("id")

        # Update the item
        update_response = self.client.put(f"/items/{item_id}", json={"name": "Updated Item", "description": "An updated test item."})
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json().get("name"), "Updated Item")

    def test_delete_item(self):
        """
        Test the item deletion endpoint to ensure it deletes the item correctly.
        """
        # First, create an item
        create_response = self.client.post("/items/", json={"name": "Test Item", "description": "A test item."})
        item_id = create_response.json().get("id")

        # Delete the item
        delete_response = self.client.delete(f"/items/{item_id}")
        self.assertEqual(delete_response.status_code, 204)

        # Ensure the item is no longer available
        get_response = self.client.get(f"/items/{item_id}")
        self.assertEqual(get_response.status_code, 404)
