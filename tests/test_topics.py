import datetime
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import daily_arxiv


def paper(index=1, title='A robot policy', code=None):
    return SimpleNamespace(
        title=title, summary='An embodied agent with a robot policy.',
        authors=['First Author', 'Last Author'], comment=code,
        entry_id=f'https://arxiv.org/abs/2611.{index:05d}v2',
        get_short_id=lambda: f'2611.{index:05d}v2',
        published=datetime.datetime(2026, 11, 10, tzinfo=datetime.timezone.utc),
        updated=datetime.datetime(2026, 11, 20, tzinfo=datetime.timezone.utc),
        primary_category='cs.RO', categories=['cs.RO', 'cs.AI'],
    )


class TopicTests(unittest.TestCase):
    def test_queries_quote_phrases_and_scope_both_title_and_abstract(self):
        query = daily_arxiv.build_query(['agentic robotics', 'robot-use'], 'cat:cs.RO')
        self.assertEqual(query, '(cat:cs.RO) AND ((ti:"agentic robotics" OR abs:"agentic robotics") OR (ti:"robot-use" OR abs:"robot-use"))')
        with self.assertRaises(ValueError):
            daily_arxiv.build_query([])

    def test_repository_config_keeps_legacy_anchors_and_agent_first(self):
        config = daily_arxiv.load_config(Path(__file__).resolve().parents[1] / 'config.yaml')
        self.assertEqual(next(iter(config['keywords'])), 'Agentic Robotics')
        self.assertTrue({'VLA', 'VLM', 'Manipulation', 'Humanoid', 'Dexterous'} <= config['keywords'].keys())
        self.assertIn('cat:cs.RO', config['kv']['VLM'])
        self.assertIn('abs:robot', config['kv']['VLM'])
        self.assertNotIn('cat:Agentic', config['kv']['Agentic Robotics'])
        for retired in ('World Models', 'Data and Evaluation'):
            self.assertNotIn(retired, config['keywords'])
            self.assertNotIn(retired, config['kv'])

    def test_fetches_more_than_twenty_and_uses_first_submission_dates(self):
        metadata = {}
        with patch.object(daily_arxiv.arxiv_client, 'results', return_value=iter([paper(i) for i in range(1, 61)])) as fetch:
            data, _ = daily_arxiv.get_daily_papers(
                'VLA', query='cat:cs.RO', max_results=100,
                start_date=datetime.date(2026, 11, 1),
                end_date=datetime.date(2026, 11, 25), metadata=metadata,
            )
        self.assertEqual(len(data['VLA']), 60)
        self.assertIn('submittedDate:[202611010000 TO 202611252359]', fetch.call_args.args[0].query)
        self.assertEqual(fetch.call_args.args[0].max_results, 101)
        self.assertIn('2026-11-10', data['VLA']['2611.00001'])
        self.assertNotIn('2026-11-20', data['VLA']['2611.00001'])
        self.assertEqual(metadata['2611.00001']['topics'], ['VLA'])

    def test_truncation_fails_explicitly(self):
        with patch.object(daily_arxiv.arxiv_client, 'results', return_value=iter([paper(1), paper(2)])):
            with self.assertRaisesRegex(RuntimeError, 'exceeded max_results'):
                daily_arxiv.get_daily_papers('Agentic Robotics', max_results=1)

    def test_local_phrase_check_rejects_stemmed_noise_but_accepts_hyphen_variants(self):
        traditional = paper(title='Multi-agent robot formation control')
        traditional.summary = 'Agents coordinate via consensus.'
        self.assertEqual(daily_arxiv.matching_terms(traditional, ['agentic']), [])
        model = paper(title='Vision-Language-Action Models for Robots')
        self.assertEqual(daily_arxiv.matching_terms(model, ['Vision Language Action']), ['Vision Language Action'])
        with patch.object(daily_arxiv.arxiv_client, 'results', return_value=iter([traditional, model])):
            data, _ = daily_arxiv.get_daily_papers('Agentic Robotics', filters=['agentic'])
        self.assertEqual(data, {'Agentic Robotics': {}})

    def test_one_paper_can_have_multiple_topics_and_escaped_table_content(self):
        metadata = {}
        with patch.object(daily_arxiv.arxiv_client, 'results', side_effect=lambda _: iter([paper(title='A | B <robot>')])):
            daily_arxiv.get_daily_papers('Agentic Robotics', metadata=metadata)
            data, _ = daily_arxiv.get_daily_papers('VLA', metadata=metadata)
        self.assertEqual(metadata['2611.00001']['topics'], ['Agentic Robotics', 'VLA'])
        self.assertEqual(metadata['2611.00001']['title'], 'A | B <robot>')
        self.assertIn('A &#124; B &lt;robot&gt;', data['VLA']['2611.00001'])

    def test_window_bootstraps_and_catches_up_after_a_long_outage(self):
        now = datetime.datetime(2026, 11, 25, tzinfo=datetime.timezone.utc)
        config = {'lookback_days': 14, 'bootstrap_days': 30}
        self.assertEqual(daily_arxiv.window_start(config, {}, now), datetime.date(2026, 11, 11))
        self.assertEqual(daily_arxiv.window_start(config, {}, now, new_topic=True), datetime.date(2026, 10, 26))
        status = {'last_successful_fetch': '2026-10-20T01:00:00+00:00'}
        self.assertEqual(daily_arxiv.window_start(config, status, now), datetime.date(2026, 10, 19))

    def test_render_orders_topics_preserves_anchors_and_uses_success_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'papers.json', Path(directory) / 'index.md'
            source.write_text(json.dumps({
                'VLA': {'2611.00001': '|row|\n'},
                'World Models': {'1': '|world model archive|\n'},
                'Data and Evaluation': {'2': '|evaluation archive|\n'},
            }))
            archived = source.read_bytes()
            daily_arxiv.json_to_md(
                source, target, to_web=True, show_badge=False,
                topics={
                    'Agentic Robotics': {'group': 'Research topics', 'description': '具身 Agent'},
                    'VLA': {'label': 'VLA and Robot Policies', 'group': 'Research topics'},
                },
                fetch_status={'last_successful_fetch': '2026-11-24T18:00:00+00:00'},
            )
            rendered = target.read_text()
            self.assertLess(rendered.index('id="agentic-robotics"'), rendered.index('id="vla"'))
            self.assertIn('[VLA and Robot Policies](#vla)', rendered)
            for retired in ('world-models', 'data-and-evaluation'):
                self.assertNotIn(f'id="{retired}"', rendered)
                self.assertNotIn(f'#{retired}', rendered)
            self.assertNotIn('Other topics', rendered)
            self.assertEqual(source.read_bytes(), archived)
            self.assertIn('暂无匹配论文', rendered)
            self.assertIn('Updated on 2026.11.25', rendered)
            self.assertIn('2026-11-25 02:00', rendered)
            self.assertIn('./README.html#usage', rendered)

    def test_render_without_config_shows_archive_but_empty_config_hides_all_topics(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'papers.json', Path(directory) / 'index.md'
            source.write_text(json.dumps({'Legacy': {'1': '|old|\n'}}))
            daily_arxiv.json_to_md(source, target, show_badge=False)
            self.assertIn('id="legacy"', target.read_text())
            daily_arxiv.json_to_md(source, target, show_badge=False, topics={})
            self.assertNotIn('id="legacy"', target.read_text())
            self.assertNotIn('#legacy', target.read_text())

    def test_new_fetch_preserves_history_and_known_code_links(self):
        old_row = '|**2026-11-10**|**Old title**|Team|[1](https://arxiv.org/abs/1)|**[link](https://github.com/a/b)**|\n'
        new_row = '|**2026-11-10**|**New title**|Team|[1](https://arxiv.org/abs/1)|null|\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'papers.json'
            path.write_text(json.dumps({'VLA': {'1': old_row, 'old': 'historical row'}}))
            daily_arxiv.update_json_file(path, [{'VLA': {'1': new_row}, 'Agentic Robotics': {'1': new_row}}])
            updated = json.loads(path.read_text())
            self.assertEqual(updated['VLA']['old'], 'historical row')
            self.assertEqual(updated['VLA']['1'], new_row.replace('null', '**[link](https://github.com/a/b)**'))
            self.assertIn('Agentic Robotics', updated)

    def test_a_failed_topic_leaves_all_outputs_and_success_status_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {key: str(root / name) for key, name in {
                'json_readme_path': 'papers.json', 'json_gitpage_path': 'web.json',
                'md_readme_path': 'README.md', 'md_gitpage_path': 'index.md',
                'json_metadata_path': 'metadata.json', 'status_path': 'status.json',
            }.items()}
            for path in paths.values():
                Path(path).write_text('{}')
            before = {path: Path(path).read_bytes() for path in paths.values()}
            config = dict(
                paths, kv={'VLA': 'vla', 'Agentic Robotics': 'agentic'}, keywords={},
                max_results=100, publish_readme=True, publish_gitpage=True,
                publish_wechat=False, show_badge=False, update_paper_links=False,
            )
            with patch.object(daily_arxiv, 'get_daily_papers', side_effect=[({'VLA': {}}, {'VLA': {}}), RuntimeError('API failed')]):
                with self.assertRaisesRegex(RuntimeError, 'API failed'):
                    daily_arxiv.demo(**config)
            self.assertEqual(before, {path: Path(path).read_bytes() for path in paths.values()})

    def test_success_publishes_cross_tags_and_render_only_does_not_advance_fetch_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = dict(
                json_readme_path=str(root / 'papers.json'), json_gitpage_path=str(root / 'web.json'),
                md_readme_path=str(root / 'README.md'), md_gitpage_path=str(root / 'index.md'),
                json_metadata_path=str(root / 'metadata.json'), status_path=str(root / 'status.json'),
                kv={'Agentic Robotics': 'agentic', 'VLA': 'vla'},
                keywords={
                    'Agentic Robotics': {'filters': ['embodied agent']},
                    'VLA': {'filters': ['robot policy']},
                },
                max_results=100, publish_readme=True, publish_gitpage=True,
                publish_wechat=False, show_badge=False, update_paper_links=False,
            )
            with patch.object(daily_arxiv.arxiv_client, 'results', side_effect=lambda _: iter([paper()])):
                daily_arxiv.demo(**config)
            metadata = daily_arxiv.read_json(config['json_metadata_path'])
            self.assertEqual(metadata['2611.00001']['topics'], ['Agentic Robotics', 'VLA'])
            self.assertEqual(metadata['2611.00001']['matched_terms']['VLA'], ['robot policy'])
            self.assertEqual(daily_arxiv.read_json(config['json_readme_path']), daily_arxiv.read_json(config['json_gitpage_path']))
            status_before = Path(config['status_path']).read_bytes()
            with patch.object(daily_arxiv.arxiv_client, 'results', side_effect=AssertionError('offline mode used network')):
                daily_arxiv.demo(**config, render_only=True)
            self.assertEqual(Path(config['status_path']).read_bytes(), status_before)


if __name__ == '__main__':
    unittest.main()
