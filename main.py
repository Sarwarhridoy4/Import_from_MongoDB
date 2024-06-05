import os
import json
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QWidget, QFileDialog, QMessageBox, QProgressBar, QDialog, QDialogButtonBox
)
from PyQt5.QtGui import QFont, QPixmap, QIcon
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from pymongo import MongoClient
from bson.json_util import dumps

# https://stackoverflow.com/questions/31836104/pyinstaller-and-onefile-how-to-include-an-image-in-the-exe-file

# Get the absolute path to the resource, works for dev and for PyInstaller
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class ExportThread(QThread):
    update_progress = pyqtSignal(int, str, int, int, float)
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, uri, db_name, output_dir):
        super().__init__()
        self.uri = uri
        self.db_name = db_name
        self.output_dir = output_dir
        self.abort_flag = False

    def run(self):
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)

            client = MongoClient(self.uri)
            db = client[self.db_name]
            collections = db.list_collection_names()
            total_collections = len(collections)
            processed_collections = 0

            if total_collections == 0:
                self.finished.emit("No collections found in the database.")
                return

            for collection_name in collections:
                if self.abort_flag:
                    self.finished.emit("Export aborted by user.")
                    return

                collection = db[collection_name]
                total_documents = collection.count_documents({})

                if total_documents > 0:
                    processed_documents = 0

                    for document in collection.find():
                        if self.abort_flag:
                            self.finished.emit("Export aborted by user.")
                            return

                        with open(os.path.join(self.output_dir, f"{self.db_name}_{collection_name}.json"), "a") as file:
                            file.write(dumps(document, indent=4) + "\n")
                            processed_documents += 1

                            # Update document progress
                            document_percentage = (processed_documents / total_documents) * 100
                            overall_percentage = ((processed_collections + (processed_documents / total_documents)) / total_collections) * 100
                            self.update_progress.emit(int(overall_percentage), collection_name, processed_documents, total_documents, document_percentage)

                processed_collections += 1

            client.close()
            self.finished.emit("Export completed successfully!")
        except Exception as e:
            self.error_occurred.emit(str(e))

    def abort(self):
        self.abort_flag = True


class MongoDBExporter(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MongoDB Exporter")
        self.setGeometry(100, 100, 600, 400)

        # Set window icon (favicon)
        self.setWindowIcon(QIcon(resource_path("./asset/favicon.png")))  # Provide the path to your favicon file

        # Main layout
        main_layout = QVBoxLayout()

        # Title and logo layout
        title_layout = QHBoxLayout()
        self.logo_label = QLabel(self)
        pixmap = QPixmap(resource_path("./asset/mongo_icon.png"))  # Provide the path to your logo image
        self.logo_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.title_label = QLabel("MongoDB Exporter", self)
        self.title_label.setFont(QFont('Arial', 18, QFont.Bold))

        title_layout.addWidget(self.logo_label)
        title_layout.addWidget(self.title_label, alignment=Qt.AlignVCenter)
        main_layout.addLayout(title_layout)

        # URI
        uri_layout = QHBoxLayout()
        self.uri_label = QLabel("MongoDB URI:", self)
        self.uri_label.setFont(QFont('Arial', 12))
        self.uri_input = QLineEdit(self)
        self.uri_input.setFont(QFont('Arial', 12))
        uri_layout.addWidget(self.uri_label)
        uri_layout.addWidget(self.uri_input)
        main_layout.addLayout(uri_layout)

        # Database Name
        db_name_layout = QHBoxLayout()
        self.db_name_label = QLabel("Database Name:", self)
        self.db_name_label.setFont(QFont('Arial', 12))
        self.db_name_input = QLineEdit(self)
        self.db_name_input.setFont(QFont('Arial', 12))
        db_name_layout.addWidget(self.db_name_label)
        db_name_layout.addWidget(self.db_name_input)
        main_layout.addLayout(db_name_layout)

        # Output Directory
        output_dir_layout = QHBoxLayout()
        self.output_dir_label = QLabel("Output Directory:", self)
        self.output_dir_label.setFont(QFont('Arial', 12))
        self.output_dir_input = QLineEdit(self)
        self.output_dir_input.setFont(QFont('Arial', 12))
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.setFont(QFont('Arial', 12))
        self.browse_button.clicked.connect(self.browse_output_dir)
        output_dir_layout.addWidget(self.output_dir_label)
        output_dir_layout.addWidget(self.output_dir_input)
        output_dir_layout.addWidget(self.browse_button)
        main_layout.addLayout(output_dir_layout)

        # Export Button
        self.export_button = QPushButton("Export", self)
        self.export_button.setFont(QFont('Arial', 12))
        self.export_button.clicked.connect(self.confirm_start_export)
        main_layout.addWidget(self.export_button, alignment=Qt.AlignCenter)

        # Abort Button
        self.abort_button = QPushButton("Abort", self)
        self.abort_button.setFont(QFont('Arial', 12))
        self.abort_button.setStyleSheet("background-color: red; color: white;")
        self.abort_button.clicked.connect(self.abort_export)
        self.abort_button.setDisabled(True)
        main_layout.addWidget(self.abort_button, alignment=Qt.AlignCenter)

        # Progress Label and Bar
        self.progress_label = QLabel("Progress: ", self)
        self.progress_label.setFont(QFont('Arial', 12))
        self.progress_bar = QProgressBar(self)
        main_layout.addWidget(self.progress_label)
        main_layout.addWidget(self.progress_bar)

        # Set central widget
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Add margins and spacing
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        self.export_thread = None

    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.output_dir_input.setText(directory)

    def confirm_start_export(self):
        reply = QMessageBox.question(
            self, 'Confirm Export', 'Are you sure you want to start the export?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.start_export()

    def start_export(self):
        uri = self.uri_input.text()
        db_name = self.db_name_input.text()
        output_dir = self.output_dir_input.text()

        if not uri or not db_name or not output_dir:
            QMessageBox.critical(self, "Error", "All fields are required!")
        else:
            self.export_button.setDisabled(True)
            self.abort_button.setDisabled(False)
            self.export_thread = ExportThread(uri, db_name, output_dir)
            self.export_thread.update_progress.connect(self.update_progress)
            self.export_thread.finished.connect(self.export_finished)
            self.export_thread.error_occurred.connect(self.export_error)
            self.export_thread.start()

    def update_progress(self, overall_percentage, collection_name, processed_documents, total_documents, document_percentage):
        self.progress_label.setText(
            f"Exporting: {collection_name}.json ({processed_documents}/{total_documents} documents) - Overall {overall_percentage:.2f}%")
        self.progress_bar.setValue(int(overall_percentage))
        QApplication.processEvents()

    def export_finished(self, message):
        self.progress_label.setText(message)
        self.export_button.setDisabled(False)
        self.abort_button.setDisabled(True)
        QMessageBox.information(self, "Success", message)

    def export_error(self, message):
        self.progress_label.setText("Error occurred!")
        self.export_button.setDisabled(False)
        self.abort_button.setDisabled(True)
        QMessageBox.critical(self, "Error", f"An error occurred: {message}")

    def abort_export(self):
        if self.export_thread:
            self.export_thread.abort()
            self.abort_button.setDisabled(True)
            self.progress_label.setText("Aborting export...")

def main():
    app = QApplication(sys.argv)
    window = MongoDBExporter()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
