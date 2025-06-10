import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (QApplication, QDialog, QTableWidget, QTableWidgetItem,
                             QPushButton, QHBoxLayout, QVBoxLayout, QLabel, QComboBox)
from https_sendRequests import HttpsRequest


class DataTableWindow(QDialog):
    def __init__(self, checktype, ip, https_port, parent=None):
        super().__init__(parent)
        self.setWindowTitle('更多异常设备')
        self.setGeometry(100, 100, 1200, 700)
        self.checktype = checktype
        self.ip = ip
        self.https_port = https_port

        # 解析数据
        query_more_url = 'https://{ip}:{https_port}/actor/healthCheck/queryViewMoreNoToken?checkType={check_type}&pageNum=1&pageSize=10'.format(
            check_type=self.checktype, ip=self.ip, https_port=self.https_port)
        data = self.get_queryCheckResult(query_more_url)
        self.total_records = data["data"]["total"]
        self.total_pages = (self.total_records + 9) // 10  # 总页数,向上取整公式

        # 分页参数
        self.current_page = 1
        self.page_size = 10
        self.page_sizes = [10, 20, 50, 100]

        self.init_ui()
        self.update_table()

    def get_queryCheckResult(self, url):
        https_request = HttpsRequest()
        result = https_request.send_request(url)
        return result

    def init_ui(self):
        """初始化界面组件"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 创建表格
        self.table = QTableWidget()
        self.init_table()
        main_layout.addWidget(self.table)

        # 分页控制布局
        pagination_layout = QHBoxLayout()

        # 上一页按钮
        self.prev_button = QPushButton("上一页")
        self.prev_button.clicked.connect(self.prev_page)
        pagination_layout.addWidget(self.prev_button)

        # 页码标签
        self.page_label = QLabel(f"第 {self.current_page} 页，共 {self.total_pages} 页，共 {self.total_records} 条记录")
        pagination_layout.addWidget(self.page_label)

        # 下一页按钮
        self.next_button = QPushButton("下一页")
        self.next_button.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.next_button)

        # 跳转到指定页
        pagination_layout.addStretch()
        self.page_input = QComboBox()
        self.page_input.addItems([str(i) for i in range(1, self.total_pages + 1)])
        self.page_input.currentTextChanged.connect(self.goto_page)
        pagination_layout.addWidget(QLabel("跳转到:"))
        pagination_layout.addWidget(self.page_input)
        pagination_layout.addWidget(QLabel("页"))

        # 每页显示数量
        pagination_layout.addStretch()
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems([str(size) for size in self.page_sizes])
        self.page_size_combo.setCurrentText(str(self.page_size))
        self.page_size_combo.currentTextChanged.connect(self.change_page_size)
        pagination_layout.addWidget(QLabel("每页显示:"))
        pagination_layout.addWidget(self.page_size_combo)
        pagination_layout.addWidget(QLabel("条"))

        main_layout.addLayout(pagination_layout)

        # 更新分页按钮状态
        self.update_pagination_buttons()

    def init_table(self):
        """初始化表格列"""
        # 设置表格列数和表头
        headers = ["操作", "检查项", "检查结果", "检查项状态", "设备名称"]

        self.table.setColumnCount(len(headers))  # 设置表格列数为5
        self.table.setHorizontalHeaderLabels(headers)  # 设置表头标题
        self.table.setWordWrap(True)  # 开启单元格自动换行
        # 设置列宽,用户可以通过鼠标拖动列边缘来手动调整列宽
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)  # 最后一列自动填充
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)  # 设置表格只读
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)  # 整行选择
        self.table.setAlternatingRowColors(True)  # 奇偶行不同颜色，提升可读性



    def update_table(self):
        """更新表格数据"""
        query_more_url = 'https://{ip}:{https_port}/actor/healthCheck/queryViewMoreNoToken?checkType={check_type}&pageNum={pn}&pageSize={ps}'.format(
            check_type=self.checktype, ip=self.ip, https_port=self.https_port, pn=self.current_page, ps=self.page_size)
        data = self.get_queryCheckResult(query_more_url)
        current_data = data["data"]["rows"]


        # 清空表格并设置行数，默认不显示数据
        self.table.setRowCount(0)
        self.table.setRowCount(len(current_data))

        # 填充数据
        for row_idx, row_data in enumerate(current_data):
            self.fill_table_row(row_idx, row_data)

        # 更新分页信息
        self.page_label.setText(f"第 {self.current_page} 页，共 {self.total_pages} 页，共 {self.total_records} 条记录")
        self.page_input.setCurrentText(str(self.current_page))


    def fill_table_row(self, row_idx, data):
        """填充单行数据"""
        field_mapping = [
            ("operation", 0),  # "operation"字段对应第0列（操作）
            ("checkContentDesc", 1),  # "checkContentDesc"对应第1列（检查项）
            ("checkResultAbnormalReason", 2),  # 对应第2列（检查结果）
            ("checkResultTypeDesc", 3),  # 对应第3列（检查项状态）
            ("checkItemDesc", 4),  # 对应第4列（设备名称）
        ]

        for field, col_idx in field_mapping:    # field=operation,col_idx=0
            value = data.get(field, "")         # 获取数据字段的值，默认空字符串
            if isinstance(value, bool):
                value = "是" if value else "否"
            elif value is None:
                value = "无"

            # 创建表格项并设置值
            item = QTableWidgetItem(str(value))

            # 设置异常项的样式（红色文本）
            if field == "checkResultTypeDesc" and value == "异常":
                item.setForeground(QtGui.QColor("red"))

            # 将表格项设置到指定行和列
            self.table.setItem(row_idx, col_idx, item)

    def prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.update_table()
            self.update_pagination_buttons()

    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.update_table()
            self.update_pagination_buttons()

    def goto_page(self, page_str):
        """跳转到指定页"""
        try:
            page = int(page_str)
            if 1 <= page <= self.total_pages:
                self.current_page = page
                self.update_table()
                self.update_pagination_buttons()
        except ValueError:
            pass

    def change_page_size(self, size_str):
        """更改每页显示数量"""
        try:
            new_size = int(size_str)
            self.page_size = new_size
            self.total_pages = (self.total_records + new_size - 1) // new_size

            # 确保当前页不超过总页数
            if self.current_page > self.total_pages:
                self.current_page = max(1, self.total_pages)

            # 更新页码下拉框
            self.page_input.clear()
            self.page_input.addItems([str(i) for i in range(1, self.total_pages + 1)])

            self.update_table()
            self.update_pagination_buttons()
        except ValueError:
            pass

    def update_pagination_buttons(self):
        """更新分页按钮状态"""
        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < self.total_pages)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DataTableWindow(checktype='device_point', ip='192.168.0.33', https_port=443)
    window.show()
    sys.exit(app.exec_())