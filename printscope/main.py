import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from printscope.ui.main_window import MainWindow

# Ensure log directory exists in user profile (AppData)
log_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'PrintScope')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "printscope.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("PrintScope")

def main():
    logger.info("Starting PrintScope...")
    # High DPI scaling is handled automatically in Qt6
    app = QApplication(sys.argv)
    app.setApplicationName("PrintScope")
    
    # Global exception handler
    def exception_hook(exctype, value, tb):
        import traceback
        err_msg = "".join(traceback.format_exception(exctype, value, tb))
        logger.error(f"Uncaught exception:\n{err_msg}")
        
        # Also show a message box if possible
        try:
            from PyQt6.QtWidgets import QMessageBox
            if QApplication.instance():
                QMessageBox.critical(None, "Critical Error", 
                    f"An unexpected error occurred:\n{value}\n\nSee logs for details.")
        except:
            pass
            
        sys.__excepthook__(exctype, value, tb)

    sys.excepthook = exception_hook
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
