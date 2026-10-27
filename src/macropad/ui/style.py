"""Folha de estilo (QSS) do aplicativo — tema escuro sóbrio."""

STYLESHEET = """
QWidget {
    background-color: #14171e;
    color: #d7dce5;
    font-size: 13px;
}
QLabel#panelTitle {
    font-size: 15px;
    font-weight: bold;
    color: #8cebff;
    padding: 4px 0;
}
QLabel#hint {
    color: #7d8595;
    font-size: 12px;
}
QPushButton {
    background-color: #232837;
    border: 1px solid #313848;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton:hover { background-color: #2c3346; }
QPushButton:pressed { background-color: #1b2030; }
QPushButton#primary {
    background-color: #145e6e;
    border-color: #1d7f94;
    font-weight: bold;
}
QPushButton#primary:hover { background-color: #187084; }
QPushButton#keyButton {
    background-color: #1b202c;
    border: 1px solid #2b3242;
    border-radius: 8px;
    font-size: 12px;
}
QPushButton#keyButton:hover { border-color: #8cebff; }
QPushButton#keyButton[bound="true"] {
    background-color: #20304a;
    border-color: #33507a;
}
QPushButton#keyButton[modeKey="true"] {
    background-color: #4a3320;
    border-color: #7a5c33;
    font-weight: bold;
}
/* Tecla pressionada no dispositivo: vence as demais por vir depois. */
QPushButton#keyButton[pressed="true"] {
    background-color: #1d7f94;
    border-color: #8cebff;
    color: #ffffff;
}
QListWidget, QLineEdit, QPlainTextEdit, QComboBox {
    background-color: #1b202c;
    border: 1px solid #2b3242;
    border-radius: 6px;
    padding: 4px;
}
QListWidget::item { padding: 6px; border-radius: 4px; }
QListWidget::item:selected { background-color: #145e6e; }
/* Sem estas regras, o marcador nativo de caixas e botões de opção é
   desenhado em tons escuros sobre o fundo escuro do tema e fica quase
   invisível — não dava para saber qual opção estava selecionada. Definir
   o subcontrole ::indicator substitui o desenho nativo, então o estado
   marcado é um preenchimento sólido e não um "✓".

   A espessura da borda tem de ser a mesma nos dois estados: o Qt aplica o
   border-radius à borda externa, e uma borda grossa quando marcado
   transformaria o círculo do botão de opção em um quadrado arredondado. */
QCheckBox, QRadioButton { spacing: 8px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px;
    height: 14px;
    background-color: #1b202c;
    border: 1px solid #4a5468;
}
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: #8cebff;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #1d7f94;
    border-color: #8cebff;
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {
    background-color: #14171e;
    border-color: #2b3242;
}
QCheckBox:disabled, QRadioButton:disabled { color: #5b6373; }
QStatusBar { color: #7d8595; }
QToolTip {
    background-color: #232837;
    color: #d7dce5;
    border: 1px solid #313848;
}
"""
