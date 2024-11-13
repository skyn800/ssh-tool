import sys
from PyQt5.QtWidgets import QApplication, QWidget, QTextEdit, QVBoxLayout, QPushButton
import os


class MyWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.text_edit = QTextEdit()
        layout.addWidget(self.text_edit)

        self.save_button = QPushButton('保存')
        layout.addWidget(self.save_button)

        self.save_button.clicked.connect(self.save_text)

        self.setLayout(layout)

    def save_text(self):
        # 获取文本编辑框中的内容
        text = self.text_edit.toPlainText()
        # 选择保存文件的路径和名称，这里简单使用当前目录下的test.txt
        file_path = os.path.join(os.getcwd(), 'test.txt')
        with open(file_path, 'w') as f:
            f.write(text)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = MyWidget()
    widget.show()
    sys.exit(app.exec_())