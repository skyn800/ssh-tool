import sys
import os
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QFileDialog, QMessageBox, QRadioButton, QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from https_sendRequests import HttpsPostRequest


class ModalDialog(QDialog):
    def __init__(self, title, ip, https_port, template_name, parent=None):
        super().__init__(parent)
        # 设置窗口置顶
        self.setWindowTitle(title)
        self.setFixedSize(500, 250)
        self.file_path = None

        self.main_layout = QVBoxLayout(self)
        # 添加文件上传框
        self.upload_label = QLabel("点击上传文件或拖动文件到此处\n仅支持.xls/.xlsx文件,大小不超过 50MB", self)
        self.upload_label.setAlignment(Qt.AlignCenter)
        self.upload_label.setStyleSheet("border: 2px dashed gray; padding: 20px; background-color: #e9f5ff;")
        self.upload_label.mousePressEvent = self.select_file
        # 启用拖放功能
        self.upload_label.setAcceptDrops(True)
        self.upload_label.dragEnterEvent = self.drag_enter_event
        self.upload_label.dropEvent = self.drop_event
        # 设置最大高度
        self.upload_label.setMaximumHeight(150)
        self.main_layout.addWidget(self.upload_label)

        # 添加超链接文字
        link_label = QLabel(f'<a href="#">{template_name}</a>')
        link_label.setOpenExternalLinks(False)
        link_label.setCursor(QCursor(Qt.PointingHandCursor))
        link_label.setAlignment(Qt.AlignRight)
        link_label.linkActivated.connect(lambda: self.download_templatefile(ip, https_port, template_name))
        self.main_layout.addWidget(link_label)


    def download_templatefile(self, ip, https_port, desc_tem):
        if desc_tem == '下载导入厂站与执行设备模板':
            download_file = '基本台账模板.xlsx'
            url = 'https://{ip}:{https_port}/account/facBasic/downLoadBasicAccountExcelTemplateNoToken'.format(ip=ip, https_port=https_port)
        elif desc_tem == '下载导入主机与平台模板':
            download_file = '主机与平台模板.xlsx'
            url = 'https://{ip}:{https_port}/account/dataInit/downSysInterfaceExcelTemplateNoToken'.format(ip=ip, https_port=https_port)
        https_post_request = HttpsPostRequest()
        response = https_post_request.send_request(url)
        # 获取桌面路径
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        file_path = os.path.join(desktop_path, download_file)

        # 创建一个询问消息框
        reply = QMessageBox.question(self, 'Question', '下载后将覆盖桌面上原来{file},是否继续?'.format(file=download_file),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            # 以二进制写入模式打开文件并保存内容
            with open(file_path, 'wb') as file:
                file.write(response.content)
                QMessageBox.information(self, '文件下载完成', f"{download_file}已下载至桌面")
        self.raise_()


    def select_file(self, event):
        file_dialog = QFileDialog()
        file_dialog.setNameFilter("Excel Files (*.xls *.xlsx)")
        if file_dialog.exec_():
            file_path = file_dialog.selectedFiles()[0]
            if os.path.getsize(file_path) > 50 * 1024 * 1024:
                QMessageBox.information(self, '超出限制', "文件大小超过 50MB，请选择其他文件。")
                return
            self.upload_label.setText(file_path)
            self.file_path = file_path

    def drag_enter_event(self, event):
        # 检查拖动的是否为文件
        if event.mimeData().hasUrls():
            file_path = event.mimeData().urls()[0].toLocalFile()
            # 检查文件格式
            if file_path.lower().endswith(('.xls', '.xlsx')):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def drop_event(self, event):
        file_path = event.mimeData().urls()[0].toLocalFile()
        if os.path.getsize(file_path) > 50 * 1024 * 1024:
            QMessageBox.information(self, '超出限制', "文件大小超过 50MB，请选择其他文件。")
            return
        self.upload_label.setText(file_path)
        self.file_path = file_path

    def get_file_path(self):
        return self.file_path



class PointModalDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(500, 400)
        self.file_path = None

        self.main_layout = QVBoxLayout(self)
        # 添加文件上传框
        self.upload_label = QLabel("点击上传文件或拖动文件到此处\n仅支持.xls/.xlsx文件,大小不超过 50MB", self)
        self.upload_label.setAlignment(Qt.AlignCenter)
        self.upload_label.setStyleSheet("border: 2px dashed gray; padding: 20px; background-color: #e9f5ff;")
        self.upload_label.mousePressEvent = self.select_file
        # 启用拖放功能
        self.upload_label.setAcceptDrops(True)
        self.upload_label.dragEnterEvent = self.drag_enter_event
        self.upload_label.dropEvent = self.drop_event
        # 设置最大高度
        self.upload_label.setMaximumHeight(150)
        self.main_layout.addWidget(self.upload_label)

    def select_file(self, event):
        file_dialog = QFileDialog()
        file_dialog.setNameFilter("Excel Files (*.xls *.xlsx)")
        if file_dialog.exec_():
            file_path = file_dialog.selectedFiles()[0]
            if os.path.getsize(file_path) > 50 * 1024 * 1024:
                QMessageBox.information(self, '超出限制', "文件大小超过 50MB，请选择其他文件。")
                return
            self.upload_label.setText(file_path)
            self.file_path = file_path

    def drag_enter_event(self, event):
        # 检查拖动的是否为文件
        if event.mimeData().hasUrls():
            file_path = event.mimeData().urls()[0].toLocalFile()
            # 检查文件格式
            if file_path.lower().endswith(('.xls', '.xlsx')):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def drop_event(self, event):
        file_path = event.mimeData().urls()[0].toLocalFile()
        if os.path.getsize(file_path) > 50 * 1024 * 1024:
            QMessageBox.information(self, '超出限制', "文件大小超过 50MB，请选择其他文件。")
            return
        self.upload_label.setText(file_path)
        self.file_path = file_path

    def get_file_path(self):
        return self.file_path






if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = ModalDialog(ip='192.168.0.33',title="选择操作", template_name='下载导入厂站与执行设备模板')
    result = dialog.exec_()
    if result == QDialog.Accepted:
        print("用户点击了确定")
    else:
        print(dialog.get_file_path())
        print("用户点击了取消")
    sys.exit(app.exec_())
