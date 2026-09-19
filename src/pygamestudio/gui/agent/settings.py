"""Settings dialog of the AI agent panel.

It stays deliberately small: pick a model, then fill in only what that model
needs.

* an online model from the list -> only the API key (the request URL belongs to
  the model name and is filled in automatically),
* a local model (Ollama) -> only the local model name, no key,
* a custom OpenAI compatible endpoint -> URL, model name and key.

Everything is stored under ``agent`` in the editor configuration file.
"""

from PySide6.QtWidgets import *

from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.agent.session import (
    DEFAULT_SETTINGS, OLLAMA_BASE_URL, OLLAMA_DEFAULT_MODEL, ONLINE_MODELS,
    PROVIDER_OLLAMA, PROVIDER_OPENAI,
)

#: The two non-preset entries of the model combo.
CHOICE_LOCAL = 'ollama'
CHOICE_CUSTOM = 'custom'


class AgentSettingsDialog(QDialog):
    """Model settings: choose a model, then only fill in what it needs."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = dict(DEFAULT_SETTINGS)
        self._settings.update(settings or {})
        self.setWindowTitle(T.tr('agent.settings_title', 'Agent settings'))
        self.setModal(True)
        self.setMinimumWidth(420)

        # One combo with the known model names: choosing a name already decides
        # the provider and the request URL, so nothing else has to be typed for
        # online models besides the key.
        self._model_combo = QComboBox()
        for name, (service, _provider, _endpoint) in ONLINE_MODELS.items():
            self._model_combo.addItem('{} ({})'.format(name, service), name)
        self._model_combo.addItem(T.tr('agent.choice_local', 'Local model (Ollama)'),
                                  CHOICE_LOCAL)
        self._model_combo.addItem(T.tr('agent.choice_custom', 'Custom (OpenAI compatible)'),
                                  CHOICE_CUSTOM)

        self._model_edit = QLineEdit(self._settings.get('model', ''))
        self._model_edit.setPlaceholderText('qwen2.5:7b')
        self._base_url_edit = QLineEdit(self._settings.get('base_url', ''))
        self._base_url_edit.setPlaceholderText('https://...')
        self._api_key_edit = QLineEdit(self._settings.get('api_key', ''))
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText('sk-...')
        self._api_key_edit.setToolTip(T.tr(
            'agent.api_key_tooltip',
            'Stored in the editor settings file on this computer and only sent to the chosen model endpoint.'))

        self._confirm_check = QCheckBox(T.tr('agent.settings_confirm',
                                             'Ask before every change'))
        self._confirm_check.setChecked(bool(self._settings.get('confirm')))
        self._confirm_check.setToolTip(T.tr(
            'agent.settings_confirm_tooltip',
            'Read-only tools always run; scene/file changes wait for your Allow.'))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(T.tr('agent.ok', 'OK'))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(T.tr('agent.cancel', 'Cancel'))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self._form = QFormLayout()
        self._form.addRow(T.tr('agent.model', 'Model'), self._model_combo)
        self._form.addRow(T.tr('agent.local_model', 'Local model'), self._model_edit)
        self._form.addRow(T.tr('agent.base_url', 'Base URL'), self._base_url_edit)
        self._form.addRow(T.tr('agent.api_key', 'API key'), self._api_key_edit)

        # The "what does this model need" text lives in the tooltip of the
        # model combo, so the dialog stays as short as possible.
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self._confirm_check)
        bottom_row.addStretch(1)
        bottom_row.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.addLayout(self._form)
        layout.addLayout(bottom_row)

        # Select first (silently), then listen, so the stored settings are not
        # overwritten by the defaults of the entry that happens to be first.
        self._select(self._detect_choice())
        self._sync()
        self._model_combo.currentIndexChanged.connect(self._on_choice_changed)

    # ------------------------------------------------------------------ state
    def _detect_choice(self):
        """The combo entry that matches the stored settings."""
        provider = (self._settings.get('provider') or PROVIDER_OPENAI).lower()
        if provider == PROVIDER_OLLAMA:
            return CHOICE_LOCAL
        base_url = (self._settings.get('base_url') or '').rstrip('/')
        for name, (_service, _provider, endpoint) in ONLINE_MODELS.items():
            if endpoint.rstrip('/') == base_url:
                return name
        return CHOICE_CUSTOM

    def _select(self, choice):
        index = self._model_combo.findData(choice)
        if index >= 0:
            self._model_combo.setCurrentIndex(index)

    def _on_choice_changed(self, index):
        """Another model was picked: prefill what that model needs."""
        choice = self._model_combo.itemData(index) or CHOICE_CUSTOM
        if choice in ONLINE_MODELS:
            self._model_edit.setText(choice)
        elif choice == CHOICE_LOCAL:
            self._model_edit.setText(OLLAMA_DEFAULT_MODEL)
        self._sync()

    def _sync(self):
        """Show exactly the fields the picked model needs (and stay compact)."""
        choice = self._model_combo.currentData() or CHOICE_CUSTOM
        online = choice in ONLINE_MODELS
        local = choice == CHOICE_LOCAL
        custom = choice == CHOICE_CUSTOM
        if online:
            self._base_url_edit.setText(ONLINE_MODELS[choice][2])
        elif local:
            self._base_url_edit.setText(OLLAMA_BASE_URL)
        self._show_row(self._model_edit, not online)
        self._show_row(self._base_url_edit, custom)
        self._show_row(self._api_key_edit, not local)
        label = self._form.labelForField(self._model_edit)
        if label is not None:
            label.setText(T.tr('agent.local_model', 'Local model') if local
                          else T.tr('agent.model', 'Model'))
        self._model_combo.setToolTip(self._tooltip_text(choice))
        # A hidden row must not leave a hole behind: the dialog follows the
        # rows that are really there, so switching models stays compact.
        self._form.activate()
        self.adjustSize()

    def _show_row(self, widget, visible):
        self._form.setRowVisible(widget, bool(visible))

    def _tooltip_text(self, choice):
        """What the picked model needs - shown when hovering the model combo."""
        if choice == CHOICE_LOCAL:
            return T.tr('agent.hint_local',
                        'Start Ollama on this computer first ({}), then enter the name of a '
                        'downloaded model - no API key is needed.').format(OLLAMA_BASE_URL)
        if choice == CHOICE_CUSTOM:
            return T.tr('agent.hint_custom',
                        'OpenAI compatible endpoint: fill in the request URL, the model name and '
                        'the key. Tool calls run inside the editor and stay undoable (Ctrl+Z).')
        return T.tr('agent.hint_online',
                    'The request URL follows the model name, so the API key is all that is '
                    'needed. Tool calls run inside the editor and stay undoable (Ctrl+Z).')

    # ---------------------------------------------------------------- result
    def result_settings(self) -> dict:
        choice = self._model_combo.currentData() or CHOICE_CUSTOM
        if choice in ONLINE_MODELS:
            provider, endpoint = ONLINE_MODELS[choice][1], ONLINE_MODELS[choice][2]
            model = choice
        elif choice == CHOICE_LOCAL:
            provider, endpoint = PROVIDER_OLLAMA, OLLAMA_BASE_URL
            model = self._model_edit.text().strip() or OLLAMA_DEFAULT_MODEL
        else:
            provider = PROVIDER_OPENAI
            endpoint = self._base_url_edit.text().strip()
            model = self._model_edit.text().strip()
        settings = dict(self._settings)
        settings.update({
            'provider': provider,
            'base_url': endpoint,
            'model': model,
            'api_key': '' if choice == CHOICE_LOCAL else self._api_key_edit.text().strip(),
            'confirm': bool(self._confirm_check.isChecked()),
        })
        return settings
