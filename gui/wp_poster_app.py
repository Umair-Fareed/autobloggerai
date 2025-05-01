#!/usr/bin/env python3
"""
WordPress Poster GUI Application

A GUI frontend for the WordPress Poster tool that allows users to customize settings,
generate articles using LLMs, and post them to WordPress sites.
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QGroupBox, QSpinBox, QCheckBox,
    QComboBox, QTextEdit, QStatusBar, QMessageBox, QFileDialog, QDoubleSpinBox,
    QFrame, QDialog, QButtonGroup, QRadioButton
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject, QSettings
from PyQt5.QtGui import QFont, QIcon

from .logging_stream import LoggingStream

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from parent package
from main import ConfigManager, AutoBlogger, Logger
from llm_provider import get_provider


class LogRedirector(QObject):
    """Redirects log messages to a QTextEdit widget"""
    new_log = pyqtSignal(str)
    
    def __init__(self, widget):
        super().__init__()
        self.widget = widget
        self.new_log.connect(self.update_log)
    
    def write(self, text):
        if text.strip():  # Avoid empty lines
            self.new_log.emit(text)
    
    def flush(self):
        pass
    
    def update_log(self, text):
        self.widget.moveCursor(QTextCursor.End)
        self.widget.insertPlainText(text)
        self.widget.moveCursor(QTextCursor.End)


# LoggingStream is now imported from .logging_stream module

class WorkerThread(QThread):
    """Worker thread for running time-consuming operations"""
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int, str)
    log_message = pyqtSignal(str)
    
    def __init__(self, autoblogger):
        super().__init__()
        self.autoblogger = autoblogger
        
        # Set up custom logging for the thread
        self.log_stream = LoggingStream()
        self.log_stream.text_written.connect(self.on_log_message)
    
    def on_log_message(self, message):
        # Forward log messages to the main thread
        self.log_message.emit(message)
        
    def run(self):
        # Setup thread-specific logging
        thread_handler = logging.StreamHandler(self.log_stream)
        thread_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger = logging.getLogger()
        logger.addHandler(thread_handler)
        
        # Send initial logging message
        logging.info("Worker thread started")
        
        try:
            # Run the actual process
            self.autoblogger.run()
            logging.info("Article generation completed successfully")
            
            # Signal completion
            self.finished.emit(True, "Process completed successfully")
        except Exception as e:
            logging.error(f"Error in worker thread: {str(e)}")
            self.finished.emit(False, str(e))
        finally:
            # Clean up the logger
            logger.removeHandler(thread_handler)


class AutoBloggerApp(QMainWindow):
    """Main application window for Auto Blogger AI"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize application settings
        self.settings = QSettings("WPPoster", "WPPosterApp")
        
        # Set up the UI
        self.init_ui()
        
        # Load configuration
        self.config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
        self.config_manager = ConfigManager(self.config_path)
        self.load_config_to_ui()
        
        # Initialize logger
        self.init_logger()
        
        # Set up auto-generation timer
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.generate_articles)
        self.next_gen_time = None
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_countdown)
        self.update_timer.start(1000)  # Update every second countdown
        # Timer will be started after first manual generation
        
        # Load and apply app settings after UI is setup
        self.apply_app_settings()
    
    def update_log(self, text):
        """Update the log display with new text"""
        if hasattr(self, 'log_output'):
            # Append text to the log output widget
            self.log_output.appendPlainText(text.rstrip())
            # Auto-scroll to the bottom
            scrollbar = self.log_output.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def apply_app_settings(self):
        # Apply theme
        theme = self.settings.value("theme", "light")
        if theme == "dark":
            self.set_application_style("dark")
        else:
            self.set_application_style()
        
        # Check if start with Windows is enabled
        start_with_windows = self.settings.value("start_with_windows", False, type=bool)
        if start_with_windows:
            # Add to startup
            self.add_to_startup()
    
    def add_to_startup(self):
        # Get the path to the executable
        executable_path = sys.executable
        
        # Get the path to the startup folder
        startup_folder = os.path.join(os.path.expanduser("~"), "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup")
        
        # Create a shortcut to the executable in the startup folder
        shortcut_path = os.path.join(startup_folder, "Auto Blogger AI.lnk")
        with open(shortcut_path, "w") as f:
            f.write("[InternetShortcut]\n")
            f.write("URL=file://" + executable_path + "\n")
            f.write("IconIndex=0\n")
            f.write("IconFile=" + executable_path + "\n")
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Auto Blogger AI")
        self.setGeometry(100, 100, 1200, 800)
        
        # Set application style
        self.set_application_style()
        
        # Set icon if available
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Create tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Create individual tabs
        self.create_settings_tab()
        self.create_article_generation_tab()
        self.create_wordpress_tab()
        self.create_llm_settings_tab()
        self.create_app_settings_tab()
        
        # Create status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
        # Create bottom buttons
        self.create_bottom_buttons(main_layout)
    
    def create_settings_tab(self):
        """Create the general settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Input file settings
        input_group = QGroupBox("Input Settings")
        input_layout = QFormLayout(input_group)
        
        # File path selection
        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(browse_btn)
        input_layout.addRow("Titles File:", file_layout)
        
        # Sheet name
        self.sheet_name_edit = QLineEdit()
        input_layout.addRow("Sheet Name:", self.sheet_name_edit)
        
        # Column names
        self.title_column_edit = QLineEdit()
        input_layout.addRow("Title Column:", self.title_column_edit)
        
        self.used_column_edit = QLineEdit()
        input_layout.addRow("Used Status Column:", self.used_column_edit)
        
        layout.addWidget(input_group)
        
        # Generation settings
        gen_group = QGroupBox("Generation Settings")
        gen_layout = QFormLayout(gen_group)
        
        # Create a layout for posting interval
        interval_layout = QHBoxLayout()
        
        # Value spinner
        self.post_interval_value = QSpinBox()
        self.post_interval_value.setRange(1, 1000)
        self.post_interval_value.setValue(24)  # Default 24 hours
        interval_layout.addWidget(self.post_interval_value)
        
        # Unit selection
        self.post_interval_unit = QComboBox()
        self.post_interval_unit.addItems(["Minutes", "Hours", "Days"])
        self.post_interval_unit.setCurrentIndex(1)  # Default to Hours
        interval_layout.addWidget(self.post_interval_unit)
        
        gen_layout.addRow("Post After Every:", interval_layout)
        
        self.randomize_check = QCheckBox("Randomize Selection")
        gen_layout.addRow("", self.randomize_check)
        
        # Image frequency control removed as requested - AI will handle image placement naturally
        
        layout.addWidget(gen_group)
        
        # Add spacer
        layout.addStretch()
        
        # Add tab
        self.tabs.addTab(tab, "General Settings")
    
    def create_article_generation_tab(self):
        """Create the article generation tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Prompt template
        prompt_group = QGroupBox("Article Generation Prompt")
        prompt_layout = QVBoxLayout(prompt_group)
        
        prompt_label = QLabel("Enter your custom prompt template. Use {title} as a placeholder for the article title:")
        prompt_layout.addWidget(prompt_label)
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(300)
        prompt_layout.addWidget(self.prompt_edit)
        
        layout.addWidget(prompt_group)
        
        # Generation buttons
        btn_layout = QHBoxLayout()
        
        self.generate_btn = QPushButton("Generate Articles")
        self.generate_btn.clicked.connect(self.generate_articles)
        btn_layout.addWidget(self.generate_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        # Add tab
        self.tabs.addTab(tab, "Article Generation")
    
    def create_wordpress_tab(self):
        """Create the WordPress settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # WordPress connection settings
        wp_group = QGroupBox("WordPress Connection")
        wp_layout = QFormLayout(wp_group)
        
        self.wp_url_edit = QLineEdit()
        wp_layout.addRow("WordPress URL:", self.wp_url_edit)
        
        self.wp_username_edit = QLineEdit()
        wp_layout.addRow("Username:", self.wp_username_edit)
        
        self.wp_password_edit = QLineEdit()
        self.wp_password_edit.setEchoMode(QLineEdit.Password)
        wp_layout.addRow("Password:", self.wp_password_edit)
        
        self.wp_app_pass_check = QCheckBox("Use Application Password")
        wp_layout.addRow("", self.wp_app_pass_check)
        
        self.wp_category_edit = QLineEdit()
        wp_layout.addRow("Category:", self.wp_category_edit)
        
        self.wp_status_combo = QComboBox()
        self.wp_status_combo.addItems(["draft", "publish", "pending", "private"])
        wp_layout.addRow("Post Status:", self.wp_status_combo)
        
        self.wp_scheduling_check = QCheckBox("Enable Future Scheduling")
        wp_layout.addRow("", self.wp_scheduling_check)
        
        layout.addWidget(wp_group)
        
        # Test connection button
        test_btn = QPushButton("Test WordPress Connection")
        test_btn.clicked.connect(self.test_wp_connection)
        layout.addWidget(test_btn)
        
        layout.addStretch()
        
        # Add tab
        self.tabs.addTab(tab, "WordPress Settings")
    
    def create_llm_settings_tab(self):
        """Create the LLM settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # LLM provider selection
        provider_group = QGroupBox("LLM Provider")
        provider_layout = QVBoxLayout(provider_group)
        
        self.provider_buttons = QButtonGroup(self)
        
        self.local_radio = QRadioButton("Local LLM (e.g., LM Studio)")
        self.gemini_radio = QRadioButton("Google Gemini API")
        
        self.provider_buttons.addButton(self.local_radio)
        self.provider_buttons.addButton(self.gemini_radio)
        
        provider_layout.addWidget(self.local_radio)
        provider_layout.addWidget(self.gemini_radio)
        
        # Connect signals to show/hide settings
        self.local_radio.toggled.connect(self.toggle_llm_settings)
        self.gemini_radio.toggled.connect(self.toggle_llm_settings)
        
        layout.addWidget(provider_group)
        
        # Local LLM settings
        self.local_group = QGroupBox("Local LLM Settings")
        local_layout = QFormLayout(self.local_group)
        
        self.local_endpoint_edit = QLineEdit()
        local_layout.addRow("API Endpoint:", self.local_endpoint_edit)
        
        self.local_model_edit = QLineEdit()
        local_layout.addRow("Model Name:", self.local_model_edit)
        
        self.local_temp_spin = QDoubleSpinBox()
        self.local_temp_spin.setRange(0.1, 1.0)
        self.local_temp_spin.setSingleStep(0.1)
        local_layout.addRow("Temperature:", self.local_temp_spin)
        
        self.local_tokens_spin = QSpinBox()
        self.local_tokens_spin.setRange(1000, 12000)
        self.local_tokens_spin.setSingleStep(100)
        local_layout.addRow("Max Tokens:", self.local_tokens_spin)
        
        layout.addWidget(self.local_group)
        
        # Gemini API settings
        self.gemini_group = QGroupBox("Google Gemini API Settings")
        gemini_layout = QFormLayout(self.gemini_group)
        
        self.gemini_key_edit = QLineEdit()
        self.gemini_key_edit.setEchoMode(QLineEdit.Password)
        gemini_layout.addRow("API Key:", self.gemini_key_edit)
        
        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.addItems(["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.0-pro"])
        gemini_layout.addRow("Model:", self.gemini_model_combo)
        
        self.gemini_temp_spin = QDoubleSpinBox()
        self.gemini_temp_spin.setRange(0.1, 1.0)
        self.gemini_temp_spin.setSingleStep(0.1)
        gemini_layout.addRow("Temperature:", self.gemini_temp_spin)
        
        self.gemini_tokens_spin = QSpinBox()
        self.gemini_tokens_spin.setRange(1000, 12000)
        self.gemini_tokens_spin.setSingleStep(100)
        gemini_layout.addRow("Max Output Tokens:", self.gemini_tokens_spin)
        
        layout.addWidget(self.gemini_group)
        
        # Test LLM button
        test_llm_btn = QPushButton("Test LLM Connection")
        test_llm_btn.clicked.connect(self.test_llm_connection)
        layout.addWidget(test_llm_btn)
        
        layout.addStretch()
        
        # Add tab
        self.tabs.addTab(tab, "LLM Settings")
    
    def create_app_settings_tab(self):
        """Create the app settings tab with application configuration options"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Application behavior settings
        behavior_group = QGroupBox("Application Behavior")
        behavior_layout = QVBoxLayout(behavior_group)
        
        # Toggle switches with modern styling
        self.startup_toggle = self.create_toggle_switch("Start with Windows", "Launch the application automatically when Windows starts")
        self.minimized_toggle = self.create_toggle_switch("Start Minimized", "Start the application minimized")
        self.notifications_toggle = self.create_toggle_switch("Show Notifications", "Display notifications when tasks complete")
        
        behavior_layout.addWidget(self.startup_toggle)
        behavior_layout.addWidget(self.minimized_toggle)
        behavior_layout.addWidget(self.notifications_toggle)
        layout.addWidget(behavior_group)
        
        # Appearance settings
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QVBoxLayout(appearance_group)
        
        # Theme selection with radio buttons
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        theme_label.setMinimumWidth(100)
        theme_layout.addWidget(theme_label)
        
        self.theme_light = QRadioButton("Light")
        self.theme_dark = QRadioButton("Dark")
        self.theme_system = QRadioButton("System Default")
        
        # Group them
        theme_group = QButtonGroup(self)
        theme_group.addButton(self.theme_light)
        theme_group.addButton(self.theme_dark)
        theme_group.addButton(self.theme_system)
        
        # Set light theme as default
        self.theme_light.setChecked(True)
        
        # Connect theme change events
        self.theme_light.toggled.connect(lambda checked: checked and self.apply_theme('Light'))
        self.theme_dark.toggled.connect(lambda checked: checked and self.apply_theme('Dark'))
        self.theme_system.toggled.connect(lambda checked: checked and self.apply_theme('System Default'))
        
        theme_layout.addWidget(self.theme_light)
        theme_layout.addWidget(self.theme_dark)
        theme_layout.addWidget(self.theme_system)
        theme_layout.addStretch()
        
        appearance_layout.addLayout(theme_layout)
        
        # Accent color selection
        accent_layout = QHBoxLayout()
        accent_label = QLabel("Accent Color:")
        accent_label.setMinimumWidth(100)
        accent_layout.addWidget(accent_label)
        
        self.accent_color = QComboBox()
        self.accent_color.addItems(["Blue", "Purple", "Green", "Orange", "Red"])
        self.accent_color.currentTextChanged.connect(self.apply_accent_color)
        accent_layout.addWidget(self.accent_color)
        accent_layout.addStretch()
        
        appearance_layout.addLayout(accent_layout)
        layout.addWidget(appearance_group)
        
        # Advanced settings
        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QVBoxLayout(advanced_group)
        
        # Log level selection
        log_level_layout = QHBoxLayout()
        log_level_label = QLabel("Log Level:")
        log_level_label.setMinimumWidth(100)
        log_level_layout.addWidget(log_level_label)
        
        self.log_level = QComboBox()
        self.log_level.addItems(["Debug", "Info", "Warning", "Error"])
        self.log_level.setCurrentIndex(1)  # Default to Info
        log_level_layout.addWidget(self.log_level)
        log_level_layout.addStretch()
        
        advanced_layout.addLayout(log_level_layout)
        
        # Max history records
        history_layout = QHBoxLayout()
        history_label = QLabel("Max History Records:")
        history_label.setMinimumWidth(100)
        history_layout.addWidget(history_label)
        
        self.max_history = QSpinBox()
        self.max_history.setRange(10, 1000)
        self.max_history.setValue(100)
        self.max_history.setSingleStep(10)
        history_layout.addWidget(self.max_history)
        history_layout.addStretch()
        
        advanced_layout.addLayout(history_layout)
        layout.addWidget(advanced_group)
        
        # Add a reset button to restore default settings
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        reset_app_settings_btn = QPushButton("Reset to Default Settings")
        reset_app_settings_btn.clicked.connect(self.reset_app_settings)
        reset_app_settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333333;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
        """)
        reset_layout.addWidget(reset_app_settings_btn)
        layout.addLayout(reset_layout)
        
        # Connect startup toggle to registry function
        self.get_toggle_checkbox(self.startup_toggle).stateChanged.connect(self.toggle_start_with_windows)
        
        # Add spacer
        layout.addStretch()
        
        # Add tab
        self.tabs.addTab(tab, "App Settings")
    
    def create_toggle_switch(self, title, description=None):
        """Create a modern toggle switch with title and optional description"""
        container = QFrame()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 8)
        
        # Text container
        text_container = QVBoxLayout()
        text_container.setContentsMargins(0, 0, 0, 0)
        text_container.setSpacing(2)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 500;")
        text_container.addWidget(title_label)
        
        # Description if provided
        if description:
            desc_label = QLabel(description)
            desc_label.setStyleSheet("color: #666666; font-size: 11px;")
            text_container.addWidget(desc_label)
            
        layout.addLayout(text_container)
        layout.addStretch()
        
        # Create a custom toggle switch
        toggle_container = QFrame()
        toggle_container.setFixedWidth(50)
        toggle_container.setFixedHeight(24)
        
        # Create the actual checkbox (hidden but functional)
        toggle = QCheckBox(toggle_container)
        toggle.move(0, 0)  # Position is not important as it will be hidden
        toggle.setChecked(False)
        toggle.setStyleSheet("opacity: 0;")  # Make it invisible
        
        # Create custom visuals for the toggle - redesigned for a cleaner look
        track = QFrame(toggle_container)
        track.setFixedWidth(44)
        track.setFixedHeight(22)
        track.move(3, 1)
        track.setStyleSheet("""
            QFrame {
                background-color: #cccccc;
                border-radius: 11px;
            }
        """)
        
        # Create the slider button - size matched to track height for a perfect fit
        slider = QFrame(toggle_container)
        slider.setFixedWidth(22)
        slider.setFixedHeight(22)
        slider.move(3, 1)  # Initial position (unchecked)
        slider.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 11px;
                border: none;
            }
        """)
        
        # Set initial state
        self.update_toggle_style(toggle, track, slider)
        
        # Connect the toggle event to update visuals
        toggle.stateChanged.connect(lambda state: self.update_toggle_style(toggle, track, slider))
        
        # Make the whole container clickable
        toggle_container.mousePressEvent = lambda event: toggle.setChecked(not toggle.isChecked())
        
        layout.addWidget(toggle_container)
        
        return container
        
    def update_toggle_style(self, toggle, track, slider):
        """Update toggle switch styling based on state"""
        if toggle.isChecked():
            # Checked state
            track.setStyleSheet("""
                QFrame {
                    background-color: #4a86e8;
                    border-radius: 11px;
                }
            """)
            slider.move(25, 1)  # Move to right
        else:
            # Unchecked state
            track.setStyleSheet("""
                QFrame {
                    background-color: #cccccc;
                    border-radius: 11px;
                }
            """)
            slider.move(3, 1)  # Move to left
    
    def reset_app_settings(self):
        """Reset application settings to defaults"""
        # Reset toggle switches
        for toggle in [self.startup_toggle, self.minimized_toggle, self.notifications_toggle]:
            self.get_toggle_checkbox(toggle).setChecked(False)
            
        self.get_toggle_checkbox(self.notifications_toggle).setChecked(True)  # Default on
        
        # Reset theme and color
        self.theme_light.setChecked(True)
        self.accent_color.setCurrentIndex(0)  # Blue
        
        # Reset advanced settings
        self.log_level.setCurrentIndex(1)  # Info
        self.max_history.setValue(100)
        
        # Apply light theme
        self.apply_theme('Light')
        
        # Show confirmation
        self.show_notification("App settings have been reset to defaults", "info")
    
    def create_bottom_buttons(self, main_layout):
        """Create the bottom buttons and footer"""
        # Add a separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #e0e0e0;")
        separator.setFixedHeight(1)
        main_layout.addWidget(separator)
        
        # Create bottom section with buttons and copyright
        bottom_section = QHBoxLayout()
        
        # Copyright text in the bottom left
        copyright_label = QLabel(" SUZA Productions. All rights reserved.")
        copyright_label.setStyleSheet("color: #888888; font-size: 11px;")
        bottom_section.addWidget(copyright_label)
        
        # Add stretch to push buttons to the right
        bottom_section.addStretch()
        
        # Button container with modern styling
        button_container = QHBoxLayout()
        button_container.setSpacing(10)
        
        # Save settings button
        save_btn = QPushButton("Save Settings")
        save_btn.setMinimumWidth(120)
        save_btn.setMinimumHeight(36)
        save_btn.clicked.connect(self.save_config)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a86e8;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #3a76d8;
            }
            QPushButton:pressed {
                background-color: #2a66c8;
            }
        """)
        button_container.addWidget(save_btn)
        
        # Reset settings button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setMinimumWidth(120)
        reset_btn.setMinimumHeight(36)
        reset_btn.clicked.connect(self.reset_config)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333333;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                background-color: #d5d5d5;
            }
        """)
        button_container.addWidget(reset_btn)
        
        # Add button container to bottom section
        bottom_section.addLayout(button_container)
        
        # Add bottom section to main layout
        main_layout.addLayout(bottom_section)
    
    def set_application_style(self, theme=None):
        """Set the application-wide styling for a modern look
        
        Args:
            theme (str, optional): The theme to apply ("dark" or None for light). Defaults to None.
        """
        # Main application style - handle dark theme if specified
        if theme == "dark":
            self.apply_theme("Dark")
            return
            
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #f9f9f9;
                color: #333333;
            }
            
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
            }
            
            QTabBar::tab {
                background-color: #f0f0f0;
                color: #555555;
                min-width: 120px;
                padding: 10px 15px;
                margin-right: 5px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: white;
                color: #4a86e8;
                font-weight: bold;
                border-top: 3px solid #4a86e8;
                border-left: 1px solid #e0e0e0;
                border-right: 1px solid #e0e0e0;
                border-bottom: none;
            }
            
            QTabBar::tab:!selected {
                border: 1px solid #e0e0e0;
                background-color: #f5f5f5;
            }
            
            QTabBar::tab:!selected:hover {
                background-color: #e8e8e8;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 1.5ex;
                background-color: white;
                padding: 15px;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #4a86e8;
            }
            
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
                selection-background-color: #4a86e8;
            }
            
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 1px solid #4a86e8;
            }
            
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px 16px;
                color: #333333;
            }
            
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            
            QCheckBox, QRadioButton {
                spacing: 8px;
            }
            
            QCheckBox::indicator, QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
            
            QStatusBar {
                background-color: #f0f0f0;
                color: #333333;
                border-top: 1px solid #e0e0e0;
            }
            
            QTextEdit#log_display {
                font-family: Consolas, Monaco, Courier, monospace;
                font-size: 11px;
                line-height: 1.3;
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 10px;
            }
            
            /* Dark mode version can be toggled via settings */
            .dark-mode QTextEdit#log_display {
                background-color: #2d3748;
                color: #f0f0f0;
                border-color: #4a5568;
            }
        """)
    
    def init_logger(self):
        """Initialize logger to redirect to console and notifications"""
        # Store the original stdout
        self.old_stdout = sys.stdout
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Create a log file path with timestamp
        log_file = os.path.join(log_dir, f'autoblogger_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        # Set up logging to both file and console
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()  # This goes to console
            ]
        )
        
        # Create custom handler to show important messages as notifications
        class NotificationHandler(logging.Handler):
            def __init__(self, app):
                super().__init__()
                self.app = app
                
            def emit(self, record):
                # Only show warnings, errors and critical messages as notifications
                if record.levelno >= logging.WARNING:
                    msg = self.format(record)
                    # Schedule notification in the main thread
                    QTimer.singleShot(0, lambda: self.app.show_notification(
                        msg, 'error' if record.levelno >= logging.ERROR else 'warning'
                    ))
        
        # Add notification handler
        notification_handler = NotificationHandler(self)
        notification_handler.setLevel(logging.WARNING)
        logging.getLogger().addHandler(notification_handler)
        
        logging.info("Auto Blogger AI started")
    
    def toggle_llm_settings(self):
        """Show/hide LLM settings based on selected provider"""
        self.local_group.setVisible(self.local_radio.isChecked())
        self.gemini_group.setVisible(self.gemini_radio.isChecked())
    
    def load_config_to_ui(self):
        """Load configuration to UI elements"""
        config = self.config_manager.config
        
        # General settings
        self.file_path_edit.setText(config.get('file_path', ''))
        self.sheet_name_edit.setText(config.get('sheet_name', ''))
        self.title_column_edit.setText(config.get('title_column', ''))
        self.used_column_edit.setText(config.get('used_column', ''))
        
        # Set post interval with proper units
        post_interval = config.get('post_interval', 24)
        post_interval_unit = config.get('post_interval_unit', 'Hours')
        self.post_interval_value.setValue(post_interval)
        unit_index = self.post_interval_unit.findText(post_interval_unit)
        if unit_index >= 0:
            self.post_interval_unit.setCurrentIndex(unit_index)
            
        self.randomize_check.setChecked(config.get('randomize', False))
        
        # Load app settings if available
        if 'app_settings' in config:
            app_settings = config['app_settings']
            
            # Load toggle switches - update with new toggle implementation
            self.get_toggle_checkbox(self.startup_toggle).setChecked(app_settings.get('start_with_windows', False))
            self.get_toggle_checkbox(self.minimized_toggle).setChecked(app_settings.get('start_minimized', False))
            self.get_toggle_checkbox(self.notifications_toggle).setChecked(app_settings.get('show_notifications', True))
            
            # Load theme option
            theme = app_settings.get('theme', 'Light')
            if theme == 'Light':
                self.theme_light.setChecked(True)
            elif theme == 'Dark':
                self.theme_dark.setChecked(True)
            elif theme == 'System Default':
                self.theme_system.setChecked(True)
            
            # Load accent color
            accent_color = app_settings.get('accent_color', 'Blue')
            accent_index = self.accent_color.findText(accent_color)
            if accent_index >= 0:
                self.accent_color.setCurrentIndex(accent_index)
                
            # Load advanced settings
            log_level = app_settings.get('log_level', 'Info')
            log_level_index = self.log_level.findText(log_level)
            if log_level_index >= 0:
                self.log_level.setCurrentIndex(log_level_index)
                
            self.max_history.setValue(app_settings.get('max_history', 100))
            
            # Apply the theme
            self.apply_theme(theme)
        
        # WordPress settings
        self.wp_url_edit.setText(config.get('wordpress', {}).get('url', ''))
        self.wp_username_edit.setText(config.get('wordpress', {}).get('username', ''))
        self.wp_password_edit.setText(config.get('wordpress', {}).get('password', ''))
        self.wp_app_pass_check.setChecked(config.get('wordpress', {}).get('use_application_password', False))
        self.wp_category_edit.setText(config.get('wordpress', {}).get('category', 'Blog'))
        
        status = config.get('wordpress', {}).get('post_status', 'draft')
        index = self.wp_status_combo.findText(status)
        if index >= 0:
            self.wp_status_combo.setCurrentIndex(index)
                
        self.wp_scheduling_check.setChecked(config.get('wordpress', {}).get('future_scheduling', False))
        
        # LLM settings
        mode = config.get('mode', 'local')
        if mode == 'gemini':
            self.gemini_radio.setChecked(True)
        else:
            self.local_radio.setChecked(True)
            
        # Local LLM settings
        self.local_endpoint_edit.setText(config.get('local', {}).get('endpoint', 'http://localhost:1234/v1/chat/completions'))
        self.local_model_edit.setText(config.get('local', {}).get('model', 'local-model'))
        self.local_temp_spin.setValue(config.get('local', {}).get('temperature', 0.7))
        self.local_tokens_spin.setValue(config.get('local', {}).get('max_tokens', 6000))
        
        # Gemini settings
        self.gemini_key_edit.setText(config.get('gemini', {}).get('api_key', ''))
        
        gemini_model = config.get('gemini', {}).get('model', 'gemini-1.5-flash')
        index = self.gemini_model_combo.findText(gemini_model)
        if index >= 0:
            self.gemini_model_combo.setCurrentIndex(index)
                
        self.gemini_temp_spin.setValue(config.get('gemini', {}).get('temperature', 0.7))
        self.gemini_tokens_spin.setValue(config.get('gemini', {}).get('max_output_tokens', 4096))
        
        # Load the article generation prompt template from config
        generation_config = config.get('generation', {})
        if 'post_template' in generation_config and generation_config['post_template']:
            self.prompt_edit.setPlainText(generation_config.get('post_template'))
        else:
            # Set a default prompt template if none exists
            default_prompt = "You are a professional content writer specializing in SEO-optimized blog posts. " 
            default_prompt += "Write a complete, polished blog article directly without any planning, thoughts, or commentary."
            default_prompt += "\n\nArticle Title: {title}"
            self.prompt_edit.setPlainText(default_prompt)
        
        # Toggle visibility
        self.toggle_llm_settings()
        
        logging.info("Configuration loaded successfully")
    
    def ui_to_config(self):
        """Convert UI elements to configuration dictionary"""
        # Make sure we have a valid configuration object
        if not hasattr(self.config_manager, 'config') or self.config_manager.config is None:
            self.config_manager.config = {}
            
        # Initialize config with existing values to avoid losing any
        config = self.config_manager.config.copy()
        
        # General settings
        config['file_path'] = self.file_path_edit.text()
        config['sheet_name'] = self.sheet_name_edit.text()
        config['title_column'] = self.title_column_edit.text()
        config['used_column'] = self.used_column_edit.text()
        config['post_interval'] = self.post_interval_value.value()
        config['post_interval_unit'] = self.post_interval_unit.currentText()
        config['randomize'] = self.randomize_check.isChecked()
        
        # App settings
        config['app_settings'] = {
            'start_with_windows': self.startup_toggle.findChild(QCheckBox).isChecked(),
            'start_minimized': self.minimized_toggle.findChild(QCheckBox).isChecked(),
            'show_notifications': self.notifications_toggle.findChild(QCheckBox).isChecked(),
            'theme': 'Light' if self.theme_light.isChecked() else
                    'Dark' if self.theme_dark.isChecked() else 'System Default',
            'accent_color': self.accent_color.currentText(),
            'log_level': self.log_level.currentText(),
            'max_history': self.max_history.value()
        }
        
        # WordPress settings
        config['wordpress'] = {
            'url': self.wp_url_edit.text(),
            'username': self.wp_username_edit.text(),
            'password': self.wp_password_edit.text(),
            'use_application_password': self.wp_app_pass_check.isChecked(),
            'category': self.wp_category_edit.text(),
            'post_status': self.wp_status_combo.currentText(),
            'future_scheduling': self.wp_scheduling_check.isChecked()
        }
        
        # LLM settings
        config['mode'] = 'gemini' if self.gemini_radio.isChecked() else 'local'
        config['local'] = {
            "endpoint": self.local_endpoint_edit.text(),
            "model": self.local_model_edit.text(),
            "temperature": self.local_temp_spin.value(),
            "max_tokens": self.local_tokens_spin.value()
        }
        
        config['gemini'] = {
            "api_key": self.gemini_key_edit.text(),
            "model": self.gemini_model_combo.currentText(),
            "temperature": self.gemini_temp_spin.value(),
            "max_output_tokens": self.gemini_tokens_spin.value()
        }
        
        config['generation'] = {
            "post_template": self.prompt_edit.toPlainText(),
            "randomize_selection": self.randomize_check.isChecked()
        }
        
        config['logging'] = {
            "log_folder": "logs"
        }
        
        return config
    
    def save_config(self):
        """Save configuration to file"""
        try:
            config = self.ui_to_config()
            
            with open(self.config_manager.config_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            self.config_manager.config = config
            logging.info("Configuration saved successfully")
            self.show_notification("Settings saved successfully", "success")
            
            # Apply app settings immediately after saving
            self.apply_app_settings()
        except Exception as e:
            logging.error(f"Error saving configuration: {e}")
            self.show_notification(f"Error saving configuration: {e}", "error")
    
    def reset_config(self):
        """Reset configuration to defaults"""
        confirm_dialog = self.create_confirmation_dialog(
            "Confirm Reset", 
            "Are you sure you want to reset all settings to defaults?",
            "This will replace your current configuration with the default values."
        )
        
        if confirm_dialog.exec_() == QDialog.Accepted:
            try:
                # Load default config
                default_config_path = os.path.join(os.path.dirname(__file__), "default_config.json")
                if os.path.exists(default_config_path):
                    with open(default_config_path, 'r') as f:
                        default_config = json.load(f)
                    
                    with open(self.config_manager.config_path, 'w') as f:
                        json.dump(default_config, f, indent=4)
                    
                    self.config_manager.config = default_config
                    self.load_config_to_ui()
                    logging.info("Configuration reset to defaults")
                    self.show_notification("Settings reset to defaults", "info")
                else:
                    raise FileNotFoundError("Default configuration file not found")
            except Exception as e:
                logging.error(f"Error resetting configuration: {e}")
                self.show_notification(f"Error resetting configuration: {e}", "error")
    
    def browse_file(self):
        """Open file dialog to select titles file"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Titles File", "", "Excel Files (*.xlsx);;CSV Files (*.csv)")
        if file_path:
            self.file_path_edit.setText(file_path)
    
    def test_wp_connection(self):
        """Test WordPress connection with current settings"""
        try:
            # Save current settings to config
            temp_config = self.ui_to_config()
            
            # Import test module and run test
            from test_wp_connection import test_wordpress_connection
            result = test_wordpress_connection(temp_config.get('wordpress', {}))
            
            if result['success']:
                QMessageBox.information(self, "Success", "WordPress connection successful!")
            else:
                QMessageBox.warning(self, "Connection Failed", f"Error: {result['message']}")
        except Exception as e:
            logging.error(f"Error testing WordPress connection: {e}")
            QMessageBox.warning(self, "Error", f"Error testing WordPress connection: {e}")
    
    def test_llm_connection(self):
        """Test LLM connection with current settings"""
        try:
            # Save current settings to config
            temp_config = self.ui_to_config()
            
            # Import test module and run test
            from test_llm_providers import test_llm_provider
            result = test_llm_provider(temp_config)
            
            if result['success']:
                QMessageBox.information(self, "Success", "LLM connection successful!")
            else:
                QMessageBox.warning(self, "Connection Failed", f"Error: {result['message']}")
        except Exception as e:
            logging.error(f"Error testing LLM connection: {e}")
            QMessageBox.warning(self, "Error", f"Error testing LLM connection: {e}")
    
    def generate_articles(self):
        """Generate articles using current settings"""
        try:
            # Save current settings
            self.save_config()
            
            # Show a notification that generation is starting
            self.show_notification("Starting article generation...", "info")
            
            # Add initial log entries
            logging.info("Starting article generation process...")
            logging.info("Loading configuration...")
            
            # Make sure UI updates
            QApplication.processEvents()
            
            # Create AutoBlogger instance
            autoblogger = AutoBlogger(self.config_manager)
            
            # Create and start worker thread
            self.worker = WorkerThread(autoblogger)
            
            # Connect signals
            self.worker.finished.connect(self.on_generation_finished)
            self.worker.log_message.connect(self.update_log_from_worker)
            
            # Log before starting
            logging.info("Configuration loaded successfully")
            logging.info("Starting content generation...")
            QApplication.processEvents()  # Ensure logs are shown
            
            # Start the worker
            self.worker.start()
            
            # Disable generate button while processing
            self.generate_btn.setEnabled(False)
            self.generate_btn.setText("Generating...")
            
            # Show progress indicator
            self.status_bar.showMessage("Generating articles...")
            
        except Exception as e:
            logging.error(f"Error starting article generation: {e}")
            QMessageBox.warning(self, "Error", f"Error starting article generation: {e}")
    
    def on_generation_finished(self, success, message):
        """Handle completion of article generation"""
        # Re-enable generate button
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Articles")
        
        # Update status
        if success:
            self.status_bar.showMessage("Article posted successfully")
            self.show_notification("Article posted to WordPress successfully!", "success")
            
            # Schedule the next automatic generation if interval is set
            interval_value = self.post_interval_value.value()
            if interval_value > 0:
                # Schedule the next generation
                self.schedule_next_generation()
                # Save configuration silently (no notification)
                try:
                    config = self.ui_to_config()
                    with open(self.config_manager.config_path, 'w') as f:
                        json.dump(config, f, indent=4)
                except Exception as e:
                    logging.error(f"Error saving configuration: {e}")
            else:
                self.status_bar.showMessage("Article posted successfully. Auto-generation is disabled (interval is 0).")
        else:
            self.status_bar.showMessage(f"Error: {message}")
            self.show_notification(f"Error generating articles: {message}", "error")
    
    def schedule_next_generation(self):
        """Schedule the next automatic article generation"""
        # Stop any existing timer
        self.auto_timer.stop()
        
        # Get the configured posting interval
        interval_value = self.post_interval_value.value()
        interval_unit = self.post_interval_unit.currentText()
        
        # Convert to milliseconds for QTimer
        if interval_unit == 'Minutes':
            ms = interval_value * 60 * 1000
            seconds = interval_value * 60
        elif interval_unit == 'Hours':
            ms = interval_value * 60 * 60 * 1000
            seconds = interval_value * 60 * 60
        else:  # Days
            ms = interval_value * 24 * 60 * 60 * 1000
            seconds = interval_value * 24 * 60 * 60
        
        # Set a minimum interval of 1 minute to avoid too frequent posting
        ms = max(ms, 60 * 1000)
        seconds = max(seconds, 60)
        
        # Store the next generation time for countdown display
        self.next_gen_time = datetime.now() + timedelta(seconds=seconds)
        
        # Start the timer
        logging.info(f"Scheduling next article generation in {interval_value} {interval_unit.lower()} ({ms/1000} seconds)")
        self.auto_timer.start(ms)
        self.update_countdown()
        
    def update_countdown(self):
        """Update the countdown timer in the status bar"""
        if self.next_gen_time is None:
            return
            
        # Calculate remaining time
        now = datetime.now()
        if now >= self.next_gen_time:
            return  # Timer should fire first
            
        remaining = self.next_gen_time - now
        
        # Format the remaining time nicely
        total_seconds = int(remaining.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            time_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            time_str = f"{minutes}m {seconds}s"
        else:
            time_str = f"{seconds}s"
            
        # Update status bar
        self.status_bar.showMessage(f"Next article will be generated in {time_str}")
    
    def update_log_from_worker(self, message):
        """Update log display with messages from worker thread"""
        # Add to log for debugging - we've removed the log tab
        print(message)
        
        # Force UI update
        QApplication.processEvents()
    
    def show_notification(self, message, message_type='info'):
        """Show an elegant notification at the bottom of the window"""
        # Create notification widget that expands with content
        notification = QFrame(self)
        notification.setObjectName("notification")
        notification.setMinimumWidth(400)
        notification.setMaximumWidth(800)  # Allow wider notifications for long messages
        
        # Set style based on type
        if message_type == 'success':
            bg_color = "#4caf50"
            icon_text = "✓"  # Check mark
            title = "Success"
        elif message_type == 'error':
            bg_color = "#f44336"
            icon_text = "✖"  # X mark
            title = "Error"
        elif message_type == 'warning':
            bg_color = "#ff9800"
            icon_text = "!"  # Exclamation mark
            title = "Warning"
        else:  # info
            bg_color = "#4a86e8"
            icon_text = "i"  # Info mark
            title = "Information"
        
        # Apply styles
        notification.setStyleSheet(f"""
            QFrame#notification {{
                background-color: white;
                color: #333333;
                border-radius: 4px;
                border-left: 4px solid {bg_color};
            }}
        """)
        
        # Create layout
        layout = QHBoxLayout(notification)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # Icon
        icon_label = QLabel()
        icon_label.setStyleSheet(f"""
            color: {bg_color};
            font-weight: bold;
            font-size: 16px;
            min-width: 20px;
        """)
        icon_label.setText(icon_text)
        layout.addWidget(icon_label)
        
        # Message content container
        msg_container = QVBoxLayout()
        msg_container.setSpacing(2)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #333333;
            font-weight: bold;
            font-size: 13px;
        """)
        msg_container.addWidget(title_label)
        
        # Message with word wrap enabled to properly expand the notification
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)  # Enable word wrapping for longer messages
        msg_label.setStyleSheet("""
            color: #555555;
            font-size: 12px;
        """)
        msg_container.addWidget(msg_label)
        
        layout.addLayout(msg_container, 1)
        
        # Close button
        close_btn = QPushButton("×")
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #aaaaaa;
                font-size: 20px;
                font-weight: bold;
                border: none;
                padding: 0px 5px;
            }
            QPushButton:hover {
                color: #333333;
            }
        """)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(notification.deleteLater)
        layout.addWidget(close_btn)
        
        # Calculate position - bottom center of window
        notification.setParent(self.centralWidget())
        notification.adjustSize()  # Ensure size adapts to content
        notification.show()
        x = (self.centralWidget().width() - notification.width()) // 2
        y = self.centralWidget().height() - notification.height() - 20
        notification.move(x, y)
        
        # Auto-remove after timeout - longer for errors
        timeout = 8000 if message_type == 'error' else 5000
        QTimer.singleShot(timeout, notification.deleteLater)
        
        return notification
    
    def get_toggle_checkbox(self, toggle_container):
        """Helper method to get the checkbox from a toggle container"""
        return toggle_container.findChild(QCheckBox)
    
    def apply_theme(self, theme):
        """Apply the selected theme to the application"""
        if theme == 'Dark':
            # Apply dark theme styles
            self.setStyleSheet("""
                QMainWindow, QDialog {
                    background-color: #292a2d;
                    color: #e8eaed;
                }
                QTabWidget::pane {
                    border: 1px solid #3c4043;
                    background-color: #292a2d;
                }
                QTabBar::tab {
                    background-color: #292a2d;
                    color: #bdc1c6;
                    padding: 8px 12px;
                    border: 1px solid #3c4043;
                    border-bottom: none;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: #3c4043;
                    color: white;
                }
                QGroupBox {
                    background-color: #202124;
                    border: 1px solid #3c4043;
                    border-radius: 4px;
                    margin-top: 1.5ex;
                    color: #e8eaed;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 8px;
                    color: #4a86e8;
                    font-weight: bold;
                    background-color: #202124;
                }
                QLabel {
                    color: #e8eaed;
                }
                QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                    background-color: #3c4043;
                    border: 1px solid #5f6368;
                    border-radius: 4px;
                    color: #e8eaed;
                    padding: 4px;
                }
                QPushButton {
                    background-color: #4a86e8;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #5a96f8;
                }
                QPushButton:pressed {
                    background-color: #3a76d8;
                }
                QCheckBox {
                    color: #e8eaed;
                }
                QRadioButton {
                    color: #e8eaed;
                }
                QStatusBar {
                    background-color: #292a2d;
                    color: #bdc1c6;
                }
            """)
            
            # Store the theme setting
            self.settings.setValue("theme", "dark")
        else:  # Light or System Default
            # Apply light theme or reset to default
            self.setStyleSheet("")  # Remove custom styles to use system default
            
            # Store the theme setting
            self.settings.setValue("theme", "light")
        
        # Apply the accent color after theme change
        self.apply_accent_color(self.accent_color.currentText())
        
    def apply_accent_color(self, color_name):
        """Apply the selected accent color to UI elements"""
        color_map = {
            'Blue': "#4a86e8",
            'Purple': "#9b5de5",
            'Green': "#00c853",
            'Orange': "#ff9800",
            'Red': "#f44336"
        }
        
        if color_name in color_map:
            color = color_map[color_name]
            # Update primary button color
            style = f"""
                QPushButton#primary {{
                    background-color: {color};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                }}
                QPushButton#primary:hover {{
                    background-color: {color}cc;  /* 80% opacity */
                }}
                QPushButton#primary:pressed {{
                    background-color: {color}99;  /* 60% opacity */
                }}
            """
            
            # Apply to primary buttons
            for button in self.findChildren(QPushButton):
                if button.objectName() == "primary":
                    button.setStyleSheet(style)
            
            # Store the accent color setting
            self.settings.setValue("accent_color", color_name)
            
    def toggle_start_with_windows(self, state):
        """Toggle whether the application starts with Windows"""
        if state:
            # Add to startup
            self.add_to_startup()
            self.settings.setValue("start_with_windows", True)
        else:
            # Remove from startup
            self.remove_from_startup()
            self.settings.setValue("start_with_windows", False)
    
    def add_to_startup(self):
        """Add application to Windows startup"""
        try:
            # Path to the current executable
            exe_path = sys.executable
            script_path = os.path.abspath(__file__)
            
            # Registry key for Windows startup
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            
            # Set registry key
            command = f'"{exe_path}" "{script_path}"'
            winreg.SetValueEx(key, "AutoBloggerAI", 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
            logging.info("Added application to Windows startup")
        except Exception as e:
            logging.error(f"Error adding to startup: {e}")
            self.show_notification(f"Could not add to startup: {e}", "error")
    
    def remove_from_startup(self):
        """Remove application from Windows startup"""
        try:
            # Registry key for Windows startup
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            
            # Delete registry key
            try:
                winreg.DeleteValue(key, "AutoBloggerAI")
            except FileNotFoundError:
                # Key doesn't exist, which is fine
                pass
                
            winreg.CloseKey(key)
            logging.info("Removed application from Windows startup")
        except Exception as e:
            logging.error(f"Error removing from startup: {e}")
            self.show_notification(f"Could not remove from startup: {e}", "error")
    
    def create_confirmation_dialog(self, title, message, description=None):
        """Create a modern confirmation dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setMinimumWidth(400)
        
        # Apply modern styling
        dialog.setStyleSheet("""
            QDialog {
                background-color: white;
                border-radius: 10px;
            }
            QLabel {
                color: #333333;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton#confirm-btn {
                background-color: #4a86e8;
                color: white;
                border: none;
            }
            QPushButton#confirm-btn:hover {
                background-color: #3a76d8;
            }
            QPushButton#cancel-btn {
                background-color: #f5f5f5;
                color: #333333;
                border: 1px solid #d0d0d0;
            }
            QPushButton#cancel-btn:hover {
                background-color: #e8e8e8;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Message
        message_label = QLabel(message)
        message_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(message_label)
        
        # Description if provided
        if description:
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #666666;")
            layout.addWidget(desc_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancel-btn")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        confirm_btn = QPushButton("Confirm")
        confirm_btn.setObjectName("confirm-btn")
        confirm_btn.clicked.connect(dialog.accept)
        confirm_btn.setDefault(True)
        button_layout.addWidget(confirm_btn)
        
        layout.addLayout(button_layout)
        
        return dialog
        
    def closeEvent(self, event):
        """Handle application close event"""
        # Restore stdout
        sys.stdout = self.old_stdout
        event.accept()


def main():
    """Main entry point for the application"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern style
    
    window = AutoBloggerApp()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
