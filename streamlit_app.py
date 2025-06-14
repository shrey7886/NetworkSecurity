import streamlit as st
import pandas as pd
import os
import sys
from dotenv import load_dotenv
import certifi
import plotly.express as px
import plotly.graph_objects as go
from networksecurity.utils.main_utils.utils import load_object
from networksecurity.utils.ml_utils.model.estimator import NetworkModel
from networksecurity.pipeline.training_pipeline import TrainingPipeline
from networksecurity.exception.exception import NetworkSecurityException

# Set page config
st.set_page_config(
    page_title="Network Security Analysis",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
    }
    .css-1d391kg {
        padding: 2rem 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# Title and description
st.title("🔒 Network Security Analysis")
st.markdown("""
    This application helps analyze network traffic data to detect potential security threats
    using machine learning. Upload your network traffic data to get predictions or train a new model.
""")

# Sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Make Predictions", "Train Model", "About"])

if page == "Home":
    st.header("Welcome to Network Security Analysis")
    st.markdown("""
        ### Features
        - 📊 Upload and analyze network traffic data
        - 🤖 Get real-time predictions using our ML model
        - 🎯 Train new models with your data
        - 📈 Visualize results and insights
        
        ### How to Use
        1. Navigate to "Make Predictions" to analyze your network traffic
        2. Upload your CSV file containing network traffic data
        3. View predictions and download results
        4. Optionally, train a new model with your data
    """)

elif page == "Make Predictions":
    st.header("Make Predictions")
    
    uploaded_file = st.file_uploader("Upload your network traffic data (CSV)", type=['csv'])
    
    if uploaded_file is not None:
        try:
            # Load data
            df = pd.read_csv(uploaded_file)
            st.success("File uploaded successfully!")
            
            # Show data preview
            st.subheader("Data Preview")
            st.dataframe(df.head())
            
            # Show basic statistics
            st.subheader("Data Statistics")
            st.write(df.describe())
            
            if st.button("Make Predictions"):
                with st.spinner("Making predictions..."):
                    try:
                        # Load model components
                        preprocessor = load_object("final_model/preprocessor.pkl")
                        final_model = load_object("final_model/model.pkl")
                        network_model = NetworkModel(preprocessor=preprocessor, model=final_model)
                        
                        # Make predictions
                        y_pred = network_model.predict(df)
                        df['predicted_threat'] = y_pred
                        
                        # Save predictions
                        output_dir = "prediction_output"
                        os.makedirs(output_dir, exist_ok=True)
                        output_path = os.path.join(output_dir, "output.csv")
                        df.to_csv(output_path, index=False)
                        
                        # Display results
                        st.success("Predictions completed!")
                        
                        # Show prediction distribution
                        st.subheader("Prediction Distribution")
                        fig = px.pie(df, names='predicted_threat', title='Threat Distribution')
                        st.plotly_chart(fig)
                        
                        # Show detailed results
                        st.subheader("Detailed Results")
                        st.dataframe(df)
                        
                        # Download button
                        st.download_button(
                            label="Download Predictions",
                            data=df.to_csv(index=False).encode('utf-8'),
                            file_name='network_security_predictions.csv',
                            mime='text/csv'
                        )
                        
                    except Exception as e:
                        st.error(f"Error making predictions: {str(e)}")
                        
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")

elif page == "Train Model":
    st.header("Train New Model")
    st.markdown("""
        This will train a new model using the latest data from the database.
        The training process may take several minutes.
    """)
    
    if st.button("Start Training"):
        try:
            with st.spinner("Training in progress..."):
                train_pipeline = TrainingPipeline()
                train_pipeline.run_pipeline()
                st.success("Training completed successfully!")
        except Exception as e:
            st.error(f"Training failed: {str(e)}")

elif page == "About":
    st.header("About This Project")
    st.markdown("""
        ### Network Security Analysis Tool
        
        This application uses machine learning to analyze network traffic and detect potential security threats.
        
        #### Technology Stack
        - Python
        - Streamlit
        - Scikit-learn
        - MongoDB
        - Plotly
        
        #### Features
        - Real-time network traffic analysis
        - Machine learning-based threat detection
        - Interactive visualizations
        - Model training capabilities
        
        #### Contact
        For support or questions, please contact the development team.
    """)

# Footer
st.markdown("---")
st.markdown("Network Security Analysis Tool | Powered by Machine Learning") 