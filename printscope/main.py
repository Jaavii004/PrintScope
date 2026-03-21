import sys
import logging
from PyQt6.QtWidgets import QApplication
from printscope.ui.main_window import MainWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("printscope.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("PrintScope")

def main():
    logger.info("Starting PrintScope...")
    app = QApplication(sys.argv)
    app.setApplicationName("PrintScope")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
