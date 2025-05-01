import sys
from PyQt5.QtCore import QObject, pyqtSignal

class LoggingStream(QObject):
    """Custom stream class that captures logging output for display in the GUI"""
    # Signal to emit when text is received
    text_written = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.buffer = ''
        
    def write(self, text):
        # Emit the text to be displayed in the GUI
        self.text_written.emit(text)
        
        # Also write to stdout for console logging
        sys.stdout.write(text)
        
    def flush(self):
        # Required for a file-like object
        pass
