import streamlit as st

class HomePage:
    """
    HomePage is responsible for rendering the home page of the Streamlit app.
    """

    def __init__(self):
        """
        Initializes the HomePage class.
        """
        self.title = "Welcome to the Streamlit App"

    def render(self) -> None:
        """
        Renders the home page with a welcome message.
        """
        st.title(self.title)
        st.write("This is the home page of the multi-page Streamlit app.")

if __name__ == "__main__":
    page = HomePage()
    page.render()