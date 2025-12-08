import streamlit as st
import pandas as pd
import logging

class AnalysisPage:
    """
    AnalysisPage is responsible for rendering the analysis page of the Streamlit app.
    """

    def __init__(self):
        """
        Initializes the AnalysisPage class.
        """
        self.title = "Data Analysis"

    def load_data(self, file_path: str) -> pd.DataFrame:
        """
        Loads data from a CSV file.

        :param file_path: Path to the CSV file.
        :return: DataFrame containing the loaded data.
        """
        try:
            data = pd.read_csv(file_path)
            return data
        except FileNotFoundError as e:
            logging.error(f"File not found: {e}")
            st.error("File not found. Please upload a valid CSV file.")
            return pd.DataFrame()
        except Exception as e:
            logging.error(f"Error loading data: {e}")
            st.error("An error occurred while loading the data.")
            return pd.DataFrame()

    def render(self) -> None:
        """
        Renders the analysis page with data upload and display functionality.
        """
        st.title(self.title)
        st.write("Upload a CSV file to analyze the data.")
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        if uploaded_file is not None:
            data = self.load_data(uploaded_file)
            st.write("Data Preview:")
            st.dataframe(data.head())

if __name__ == "__main__":
    page = AnalysisPage()
    page.render()