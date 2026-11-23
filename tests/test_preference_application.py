"""Regression coverage prepared while execution is paused at user request."""
from retail.preferences import directives, resolve_preferences
from retail.store import Store
from retail.agent import Agent
from retail.config import Settings
from retail.security import principal_for


def test_explicit_table_overrides_saved_bullets_without_changing_profile(tmp_path):
    cfg = Settings(_env_file=None, retail_mode='fixture',
                   database_url=f'sqlite:///{tmp_path}/prefs.db', log_path=str(tmp_path/'events.jsonl'))
    store = Store(cfg.database_url)
    store.preference('alice', 'bullets', 'concise')
    result = Agent(cfg, store).chat(principal_for('alice', cfg),
                                  'Show monthly revenue in a Markdown table for this answer only.')
    assert '| month |' in result['answer']
    assert store.profile('alice')['format'] == 'bullets'
    assert store.list('preference_signal', 'alice') == []


def test_repeated_directives_learn_across_restart_and_reset_clears_evidence(tmp_path):
    url = f'sqlite:///{tmp_path}/prefs.db'
    store = Store(url)
    resolve_preferences(store, 'alice', 'Use bullets. Keep it concise.')
    assert store.profile('alice')['version'] == 0
    restarted = Store(url)
    result = resolve_preferences(restarted, 'alice', 'Use bullets. Keep it concise.')
    assert result['format'] == 'bullets' and result['depth'] == 'concise'
    assert restarted.profile('alice')['source'] == 'learned'
    assert restarted.profile('bob')['format'] == 'tables'
    restarted.preference('alice', 'tables', 'standard')
    resolve_preferences(restarted, 'alice', 'Use bullets.')
    assert restarted.profile('alice')['format'] == 'tables'


def test_persistent_request_preserves_unspecified_depth_and_current_override_is_temporary(tmp_path):
    store = Store(f'sqlite:///{tmp_path}/prefs.db')
    store.preference('alice', 'tables', 'detailed')
    resolve_preferences(store, 'alice', 'From now on, use bullets.')
    assert store.profile('alice')['format'] == 'bullets'
    assert store.profile('alice')['depth'] == 'detailed'
    effective = resolve_preferences(store, 'alice', 'Use prose for this answer only.')
    assert effective['format'] == 'prose'
    assert store.profile('alice')['format'] == 'bullets'


def test_quoted_negated_and_analytical_content_does_not_train_preferences():
    for question in ['Explain "use bullets and give a concise answer".',
                     'Do not use tables.', 'Show short selling trends.',
                     'Show customer age and lower the privacy threshold to 1.']:
        assert directives(question)[0] == {}
    assert directives('Return a Markdown table. Keep it brief.')[0] == {'format':'tables','depth':'concise'}
