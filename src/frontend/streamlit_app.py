# src/frontend/streamlit_app.py
import streamlit as st
import requests
import os
import logging
import traceback
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import json
from dotenv import load_dotenv
from datetime import datetime
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chatbot_app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Global PDF variables (hardcoded)
CURRENT_PDF_UUID = "39089c73"
CURRENT_PDF_NAME = "The_FIFA_World_Cup__A_Historical_Journey-1_1.pdf"
PDF_DISPLAY_NAME = "The_FIFA_World_Cup__A_Historical_Journey-1_1.pdf"

# Backend URLs
CHATBOT_BACKEND_URL = os.getenv('CHATBOT_BACKEND_URL')

@dataclass
class ChatResponse:
    """Data class for API chat response"""
    answer: str

@dataclass
class GenericRAGResponse:
    """Data class for GenericRAG chat response"""
    response: str

class AppError(Exception):
    """Base exception class for application errors"""
    def __init__(self, message: str, error_code: str = None, details: Dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class APIError(AppError):
    """Exception for API-related errors"""
    pass

class ValidationError(AppError):
    """Exception for validation errors"""
    pass

class ConfigurationError(AppError):
    """Exception for configuration errors"""
    pass

class ErrorHandler:
    """Centralized error handling and logging"""
    
    @staticmethod
    def log_error(error: Exception, context: str = "", user_message: str = None):
        """Log error with context and return user-friendly message"""
        error_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        # Log detailed error information
        logger.error(f"Error ID: {error_id}")
        logger.error(f"Context: {context}")
        logger.error(f"Error Type: {type(error).__name__}")
        logger.error(f"Error Message: {str(error)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Display user-friendly error in Streamlit
        if user_message:
            st.error(f"❌ {user_message}")
        else:
            st.error(f"❌ An error occurred. Error ID: {error_id}")
        
        # Show detailed error in debug mode
        if st.session_state.get('debug_mode', False):
            with st.expander(f"🐛 Debug Info (Error ID: {error_id})"):
                st.code(f"Error Type: {type(error).__name__}")
                st.code(f"Error Message: {str(error)}")
                st.code(f"Context: {context}")
                if hasattr(error, 'details') and error.details:
                    st.json(error.details)
        
        return error_id

class APIClient:
    """Handles all API communications with enhanced error handling"""
    
    def __init__(self):
        self.endpoint = self._validate_endpoint()
        self.chatbot_backend_url = self._validate_chatbot_backend()
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Streamlit-PDF-Chatbot/1.0'
        })
        
        # Test connection on initialization
        self._test_connection()
    
    def _validate_endpoint(self) -> str:
        """Validate and return the API endpoint"""
        endpoint = os.getenv('ENDPOINT')
        
        if not endpoint:
            error = ConfigurationError(
                "ENDPOINT environment variable not set",
                "MISSING_ENDPOINT",
                {"env_file_exists": os.path.exists('.env')}
            )
            ErrorHandler.log_error(
                error, 
                "API Client Initialization",
                "Configuration error: Please check your .env file"
            )
            raise error
        
        # Validate URL format
        if not endpoint.startswith(('http://', 'https://')):
            error = ConfigurationError(
                f"Invalid endpoint format: {endpoint}",
                "INVALID_ENDPOINT_FORMAT",
                {"endpoint": endpoint}
            )
            ErrorHandler.log_error(
                error,
                "API Client Initialization",
                "Invalid endpoint URL format in configuration"
            )
            raise error
        
        logger.info(f"API endpoint configured: {endpoint}")
        return endpoint.rstrip('/')
    
    def _validate_chatbot_backend(self) -> str:
        """Validate and return the chatbot backend URL"""
        chatbot_url = CHATBOT_BACKEND_URL
        
        if not chatbot_url:
            logger.warning("CHATBOT_BACKEND_URL environment variable not set")
            return None
        
        # Validate URL format
        if not chatbot_url.startswith(('http://', 'https://')):
            logger.warning(f"Invalid chatbot backend URL format: {chatbot_url}")
            return None
        
        logger.info(f"Chatbot backend URL configured: {chatbot_url}")
        return chatbot_url.rstrip('/')


    def _test_connection(self):
        """Test basic connectivity to the API endpoint"""
        try:
            # Try a simple HEAD request to test connectivity
            response = requests.head(self.endpoint, timeout=5)
            logger.info(f"Connection test successful. Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Connection test failed: {str(e)}")
            # Don't raise error here, just log the warning
    
    def send_query(self, query: str, pdf_uuid: str = None) -> Optional[ChatResponse]:
        """Send user query to the answer endpoint with comprehensive error handling"""
        if not query or not query.strip():
            error = ValidationError(
                "Query cannot be empty",
                "EMPTY_QUERY"
            )
            ErrorHandler.log_error(
                error,
                "Query Validation",
                "Please enter a valid question"
            )
            return None
        
        try:
            url = f"{self.endpoint}/answer"
            payload = {"query": query.strip()}
            if pdf_uuid:
                payload["pdf_uuid"] = pdf_uuid
            
            logger.info(f"Sending query to {url}")
            logger.debug(f"Query payload: {payload}")
            
            response = self.session.post(
                url,
                json=payload,
                timeout=30
            )
            
            logger.info(f"Response status: {response.status_code}")
            
            # Handle different HTTP status codes
            if response.status_code == 404:
                raise APIError(
                    "Answer endpoint not found",
                    "ENDPOINT_NOT_FOUND",
                    {"url": url, "status_code": response.status_code}
                )
            elif response.status_code == 500:
                raise APIError(
                    "Server error occurred",
                    "SERVER_ERROR",
                    {"url": url, "status_code": response.status_code}
                )
            elif response.status_code != 200:
                raise APIError(
                    f"Unexpected status code: {response.status_code}",
                    "UNEXPECTED_STATUS",
                    {"url": url, "status_code": response.status_code}
                )
            
            response.raise_for_status()
            
            # Parse JSON response
            try:
                data = response.json()
                logger.debug(f"Response data: {data}")
            except json.JSONDecodeError as e:
                raise APIError(
                    "Invalid JSON response from server",
                    "INVALID_JSON",
                    {"response_text": response.text[:500]}
                )
            
            # Validate response structure
            required_fields = ['answer']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                raise APIError(
                    f"Missing required fields in response: {missing_fields}",
                    "MISSING_RESPONSE_FIELDS",
                    {"missing_fields": missing_fields, "response_data": data}
                )
            
            # Create response object with only the answer field
            chat_response = ChatResponse(
                answer=data.get('answer', '')
            )
            
            logger.info("Query processed successfully")
            return chat_response
            
        except requests.exceptions.Timeout as e:
            error = APIError(
                "Request timed out",
                "TIMEOUT",
                {"timeout": 30, "url": url}
            )
            ErrorHandler.log_error(
                error,
                "API Query Request",
                "The request took too long. Please try again."
            )
            return None
            
        except requests.exceptions.ConnectionError as e:
            error = APIError(
                "Cannot connect to API server",
                "CONNECTION_ERROR",
                {"endpoint": self.endpoint}
            )
            ErrorHandler.log_error(
                error,
                "API Query Request",
                "Cannot connect to the server. Please check your internet connection."
            )
            return None
            
        except APIError:
            # Re-raise API errors as they're already handled
            raise
            
        except Exception as e:
            error = APIError(
                f"Unexpected error during query: {str(e)}",
                "UNEXPECTED_ERROR",
                {"error_type": type(e).__name__}
            )
            ErrorHandler.log_error(
                error,
                "API Query Request",
                "An unexpected error occurred. Please try again."
            )
            return None
    
    def send_generic_rag_query(self, query: str) -> Optional[GenericRAGResponse]:
        """Send query to GenericRAG backend"""
        if not self.chatbot_backend_url:
            logger.warning("GenericRAG backend not configured")
            return None
            
        if not query or not query.strip():
            return None
        
        try:
            url = f"{self.chatbot_backend_url}/chat"
            payload = {"query": query.strip()}
            
            logger.info(f"Sending GenericRAG query to {url}")
            
            response = self.session.post(
                url,
                json=payload,
                timeout=30
            )
            
            logger.info(f"GenericRAG response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"GenericRAG unexpected status code: {response.status_code}")
                return None
            
            response.raise_for_status()
            
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON response from GenericRAG")
                return None
            
            if 'response' not in data:
                logger.error("Missing 'response' field in GenericRAG response")
                return None
            
            generic_response = GenericRAGResponse(
                response=data.get('response', '')
            )
            
            logger.info("GenericRAG query processed successfully")
            return generic_response
            
        except requests.exceptions.Timeout:
            logger.error("GenericRAG request timed out")
            return None
            
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to GenericRAG server")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error during GenericRAG query: {str(e)}")
            return None

class ChatUI:
    """Handles chat interface rendering and state management with error handling"""
    
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
        self._initialize_session_state()
    
    def _initialize_session_state(self):
        """Initialize session state variables"""
        try:
            if "messages" not in st.session_state:
                st.session_state.messages = []
            if "hybrid_responses" not in st.session_state:
                st.session_state.hybrid_responses = []
            if "generic_responses" not in st.session_state:
                st.session_state.generic_responses = []
            if "suggested_questions" not in st.session_state:
                st.session_state.suggested_questions = []
            if "debug_mode" not in st.session_state:
                st.session_state.debug_mode = False
            if "error_count" not in st.session_state:
                st.session_state.error_count = 0
            if 'current_pdf_uuid' not in st.session_state:
                st.session_state.current_pdf_uuid = CURRENT_PDF_UUID
            if 'current_pdf_name' not in st.session_state:
                st.session_state.current_pdf_name = CURRENT_PDF_NAME
            if 'pdf_display_name' not in st.session_state:
                st.session_state.pdf_display_name = PDF_DISPLAY_NAME
                
            logger.info("Session state initialized successfully")
        except Exception as e:
            ErrorHandler.log_error(
                e,
                "Session State Initialization",
                "Failed to initialize application state"
            )
    
    def display_chat_history(self):
        """Display all chat messages with error handling"""
        try:
            assistant_response_count = 0
            
            for idx, message in enumerate(st.session_state.messages):
                if message["role"] == "user":
                    with st.chat_message(message["role"]):
                        st.write(message["content"])
                elif message["role"] == "assistant":
                    if message["content"] == "dual_response":
                        # Display dual response layout
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("### 🔄 GenericRAG")
                            with st.chat_message("assistant"):
                                if assistant_response_count < len(st.session_state.generic_responses):
                                    st.write(st.session_state.generic_responses[assistant_response_count])
                        
                        with col2:
                            st.markdown("### ⚡ HybridRAG")
                            with st.chat_message("assistant"):
                                if assistant_response_count < len(st.session_state.hybrid_responses):
                                    st.write(st.session_state.hybrid_responses[assistant_response_count])
                        
                        assistant_response_count += 1
                    else:
                        # Display regular single response (for backward compatibility)
                        with st.chat_message(message["role"]):
                            st.write(message["content"])
                            
                            # Display enrollment prompt if applicable
                            if message.get("show_enroll"):
                                st.info("💡 Would you like to enroll for more information?")
                                
        except Exception as e:
            ErrorHandler.log_error(
                e,
                "Chat History Display",
                "Error displaying chat history"
            )
    
    def _handle_user_input(self, user_input: str):
        """Process user input and get response with comprehensive error handling"""
        try:
            # Validate input
            if not user_input or not user_input.strip():
                st.warning("Please enter a valid question.")
                return
            
            # Add user message to chat
            st.session_state.messages.append({
                "role": "user", 
                "content": user_input.strip()
            })
            
            # Get responses from both backends
            with st.spinner("Getting responses from both architectures..."):
                # Get HybridRAG response
                hybrid_response = self.api_client.send_query(user_input.strip(), st.session_state.current_pdf_uuid)
                
                # Get GenericRAG response
                generic_response = self.api_client.send_generic_rag_query(user_input.strip())
            
            # Store responses
            hybrid_answer = hybrid_response.answer if hybrid_response else "Error: Unable to get response from HybridRAG"
            generic_answer = generic_response.response if generic_response else "Error: Unable to get response from GenericRAG"
            
            st.session_state.hybrid_responses.append(hybrid_answer)
            st.session_state.generic_responses.append(generic_answer)
            
            # Add placeholder message (actual responses will be shown in dual layout)
            st.session_state.messages.append({
                "role": "assistant", 
                "content": "dual_response"  # Special marker for dual response display
            })
            
            # Reset error count on successful response
            st.session_state.error_count = 0
                
        except Exception as e:
            ErrorHandler.log_error(
                e,
                "User Input Handling",
                "Error processing your message"
            )
    
    def render_chat_interface(self):
        """Render the main chat interface with error boundaries"""
        try:
            st.title("🤖 PDF Assistant Chatbot")
            
            # Display current PDF indicator
            if st.session_state.current_pdf_uuid:
                st.info(f"📄 Currently querying: **{st.session_state.pdf_display_name}**")
            else:
                st.warning("⚠️ No PDF uploaded. Please upload a PDF first for document-specific queries.")
            
            # Display architecture comparison header
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 🔄 GenericRAG Architecture")
            with col2:
                st.markdown("### ⚡ HybridRAG Architecture")
            
            st.markdown("---")
            
            # Display chat history
            self.display_chat_history()
            
            # Chat input
            if prompt := st.chat_input("Ask me anything about your documents..."):
                self._handle_user_input(prompt)
                st.rerun()
            
        except Exception as e:
            ErrorHandler.log_error(
                e,
                "Chat Interface Rendering",
                "Error rendering chat interface"
            )


class StreamlitApp:
    """Main application class with comprehensive error handling"""
    
    def __init__(self):
        self._configure_page()
        self._setup_error_handling()
        self.api_client = self._initialize_api_client()
        if self.api_client:
            self.chat_ui = ChatUI(self.api_client)
    
    def _configure_page(self):
        """Configure Streamlit page settings"""
        try:
            st.set_page_config(
                page_title="PDF Assistant Chatbot",
                page_icon="🤖",
                layout="wide",
                initial_sidebar_state="expanded"
            )
            logger.info("Streamlit page configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure Streamlit page: {str(e)}")
    
    def _setup_error_handling(self):
        """Setup global error handling"""
        try:
            # Create logs directory if it doesn't exist
            os.makedirs('logs', exist_ok=True)
            logger.info("Error handling setup completed")
        except Exception as e:
            logger.error(f"Failed to setup error handling: {str(e)}")
    
    def _initialize_api_client(self) -> Optional[APIClient]:
        """Initialize API client with error handling"""
        try:
            return APIClient()
        except ConfigurationError as e:
            # Configuration errors are already handled by ErrorHandler
            st.info("Please check the troubleshooting guide below:")
            with st.expander("🔧 Configuration Help"):
                st.markdown("""
                **Setup Steps:**
                1. Create a `.env` file in your project directory
                2. Add your endpoint: `ENDPOINT=https://your-api-endpoint.com`
                3. Restart the application
                
                **File Structure:**
                ```
                your-project/
                ├── app.py
                ├── .env          ← Create this file
                ├── requirements.txt
                └── README.md
                ```
                """)
            st.stop()
        except Exception as e:
            ErrorHandler.log_error(
                e,
                "API Client Initialization",
                "Failed to initialize the application"
            )
            st.stop()
    
    def run(self):
        """Run the main application with error boundaries"""
        try:
            
            # Render main chat interface
            self.chat_ui.render_chat_interface()
            
        except Exception as e:
            ErrorHandler.log_error(
                e,
                "Main Application",
                "Critical application error"
            )
            st.error("A critical error occurred. Please refresh the page.")
    

def main():
    """Application entry point with top-level error handling"""
    try:
        logger.info("Starting PDF Assistant Chatbot application")
        app = StreamlitApp()
        app.run()
    except Exception as e:
        logger.critical(f"Critical application failure: {str(e)}")
        logger.critical(f"Traceback: {traceback.format_exc()}")
        st.error("🚨 Critical application error. Please check the logs and restart.")

if __name__ == "__main__":
    main()