# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from datetime import datetime
from unittest.mock import Mock, patch
import uuid

import pandas as pd

from superset import app
from superset.exceptions import SpatialException
from superset.utils.core import DTTM_ALIAS
import superset.viz as viz
from .base_tests import SupersetTestCase
from .utils import load_fixture


class BaseVizTestCase(SupersetTestCase):

    def test_constructor_exception_no_datasource(self):
        form_data = {}
        datasource = None
        with self.assertRaises(Exception):
            viz.BaseViz(datasource, form_data)

    def test_process_metrics(self):
        # test TableViz metrics in correct order
        form_data = {
            'url_params': {},
            'row_limit': 500,
            'metric': 'sum__SP_POP_TOTL',
            'entity': 'country_code',
            'secondary_metric': 'sum__SP_POP_TOTL',
            'granularity_sqla': 'year',
            'page_length': 0,
            'all_columns': [],
            'viz_type': 'table',
            'since': '2014-01-01',
            'until': '2014-01-02',
            'metrics': [
                'sum__SP_POP_TOTL',
                'SUM(SE_PRM_NENR_MA)',
                'SUM(SP_URB_TOTL)',
            ],
            'country_fieldtype': 'cca3',
            'percent_metrics': [
                'count',
            ],
            'slice_id': 74,
            'time_grain_sqla': None,
            'order_by_cols': [],
            'groupby': [
                'country_name',
            ],
            'compare_lag': '10',
            'limit': '25',
            'datasource': '2__table',
            'table_timestamp_format': '%Y-%m-%d %H:%M:%S',
            'markup_type': 'markdown',
            'where': '',
            'compare_suffix': 'o10Y',
        }
        datasource = Mock()
        datasource.type = 'table'
        test_viz = viz.BaseViz(datasource, form_data)
        expect_metric_labels = [u'sum__SP_POP_TOTL',
                                u'SUM(SE_PRM_NENR_MA)',
                                u'SUM(SP_URB_TOTL)',
                                u'count',
                                ]
        self.assertEqual(test_viz.metric_labels, expect_metric_labels)
        self.assertEqual(test_viz.all_metrics, expect_metric_labels)

    def test_get_df_returns_empty_df(self):
        form_data = {'dummy': 123}
        query_obj = {'granularity': 'day'}
        datasource = self.get_datasource_mock()
        test_viz = viz.BaseViz(datasource, form_data)
        result = test_viz.get_df(query_obj)
        self.assertEqual(type(result), pd.DataFrame)
        self.assertTrue(result.empty)

    def test_get_df_handles_dttm_col(self):
        form_data = {'dummy': 123}
        query_obj = {'granularity': 'day'}
        results = Mock()
        results.query = Mock()
        results.status = Mock()
        results.error_message = Mock()
        datasource = Mock()
        datasource.type = 'table'
        datasource.query = Mock(return_value=results)
        mock_dttm_col = Mock()
        datasource.get_col = Mock(return_value=mock_dttm_col)

        test_viz = viz.BaseViz(datasource, form_data)
        test_viz.df_metrics_to_num = Mock()
        test_viz.get_fillna_for_columns = Mock(return_value=0)

        results.df = pd.DataFrame(data={DTTM_ALIAS: ['1960-01-01 05:00:00']})
        datasource.offset = 0
        mock_dttm_col = Mock()
        datasource.get_col = Mock(return_value=mock_dttm_col)
        mock_dttm_col.python_date_format = 'epoch_ms'
        result = test_viz.get_df(query_obj)
        print(result)
        import logging
        logging.info(result)
        pd.testing.assert_series_equal(
            result[DTTM_ALIAS],
            pd.Series([datetime(1960, 1, 1, 5, 0)], name=DTTM_ALIAS),
        )

        mock_dttm_col.python_date_format = None
        result = test_viz.get_df(query_obj)
        pd.testing.assert_series_equal(
            result[DTTM_ALIAS],
            pd.Series([datetime(1960, 1, 1, 5, 0)], name=DTTM_ALIAS),
        )

        datasource.offset = 1
        result = test_viz.get_df(query_obj)
        pd.testing.assert_series_equal(
            result[DTTM_ALIAS],
            pd.Series([datetime(1960, 1, 1, 6, 0)], name=DTTM_ALIAS),
        )

        datasource.offset = 0
        results.df = pd.DataFrame(data={DTTM_ALIAS: ['1960-01-01']})
        mock_dttm_col.python_date_format = '%Y-%m-%d'
        result = test_viz.get_df(query_obj)
        pd.testing.assert_series_equal(
            result[DTTM_ALIAS],
            pd.Series([datetime(1960, 1, 1, 0, 0)], name=DTTM_ALIAS),
        )

    def test_cache_timeout(self):
        datasource = self.get_datasource_mock()
        datasource.cache_timeout = 0
        test_viz = viz.BaseViz(datasource, form_data={})
        self.assertEqual(0, test_viz.cache_timeout)

        datasource.cache_timeout = 156
        test_viz = viz.BaseViz(datasource, form_data={})
        self.assertEqual(156, test_viz.cache_timeout)

        datasource.cache_timeout = None
        datasource.database.cache_timeout = 0
        self.assertEqual(0, test_viz.cache_timeout)

        datasource.database.cache_timeout = 1666
        self.assertEqual(1666, test_viz.cache_timeout)

        datasource.database.cache_timeout = None
        test_viz = viz.BaseViz(datasource, form_data={})
        self.assertEqual(app.config['CACHE_DEFAULT_TIMEOUT'], test_viz.cache_timeout)


class TableVizTestCase(SupersetTestCase):

    def test_get_data_applies_percentage(self):
        form_data = {
            'percent_metrics': [{
                'expressionType': 'SIMPLE',
                'aggregate': 'SUM',
                'label': 'SUM(value1)',
                'column': {'column_name': 'value1', 'type': 'DOUBLE'},
            }, 'avg__B'],
            'metrics': [{
                'expressionType': 'SIMPLE',
                'aggregate': 'SUM',
                'label': 'SUM(value1)',
                'column': {'column_name': 'value1', 'type': 'DOUBLE'},
            }, 'count', 'avg__C'],
        }
        datasource = self.get_datasource_mock()
        raw = {}
        raw['SUM(value1)'] = [15, 20, 25, 40]
        raw['avg__B'] = [10, 20, 5, 15]
        raw['avg__C'] = [11, 22, 33, 44]
        raw['count'] = [6, 7, 8, 9]
        raw['groupA'] = ['A', 'B', 'C', 'C']
        raw['groupB'] = ['x', 'x', 'y', 'z']
        df = pd.DataFrame(raw)
        test_viz = viz.TableViz(datasource, form_data)
        data = test_viz.get_data(df)
        # Check method correctly transforms data and computes percents
        self.assertEqual(set([
            'groupA', 'groupB', 'count',
            'SUM(value1)', 'avg__C',
            '%SUM(value1)', '%avg__B',
        ]), set(data['columns']))
        expected = [
            {
                'groupA': 'A', 'groupB': 'x',
                'count': 6, 'SUM(value1)': 15, 'avg__C': 11,
                '%SUM(value1)': 0.15, '%avg__B': 0.2,
            },
            {
                'groupA': 'B', 'groupB': 'x',
                'count': 7, 'SUM(value1)': 20, 'avg__C': 22,
                '%SUM(value1)': 0.2, '%avg__B': 0.4,
            },
            {
                'groupA': 'C', 'groupB': 'y',
                'count': 8, 'SUM(value1)': 25, 'avg__C': 33,
                '%SUM(value1)': 0.25, '%avg__B': 0.1,
            },
            {
                'groupA': 'C', 'groupB': 'z',
                'count': 9, 'SUM(value1)': 40, 'avg__C': 44,
                '%SUM(value1)': 0.40, '%avg__B': 0.3,
            },
        ]
        self.assertEqual(expected, data['records'])

    def test_parse_adhoc_filters(self):
        form_data = {
            'metrics': [{
                'expressionType': 'SIMPLE',
                'aggregate': 'SUM',
                'label': 'SUM(value1)',
                'column': {'column_name': 'value1', 'type': 'DOUBLE'},
            }],
            'adhoc_filters': [
                {
                    'expressionType': 'SIMPLE',
                    'clause': 'WHERE',
                    'subject': 'value2',
                    'operator': '>',
                    'comparator': '100',
                },
                {
                    'expressionType': 'SIMPLE',
                    'clause': 'HAVING',
                    'subject': 'SUM(value1)',
                    'operator': '<',
                    'comparator': '10',
                },
                {
                    'expressionType': 'SQL',
                    'clause': 'HAVING',
                    'sqlExpression': 'SUM(value1) > 5',
                },
                {
                    'expressionType': 'SQL',
                    'clause': 'WHERE',
                    'sqlExpression': 'value3 in (\'North America\')',
                },
            ],
        }
        datasource = self.get_datasource_mock()
        test_viz = viz.TableViz(datasource, form_data)
        query_obj = test_viz.query_obj()
        self.assertEqual(
            [{'col': 'value2', 'val': '100', 'op': '>'}],
            query_obj['filter'],
        )
        self.assertEqual(
            [{'op': '<', 'val': '10', 'col': 'SUM(value1)'}],
            query_obj['extras']['having_druid'],
        )
        self.assertEqual('(value3 in (\'North America\'))', query_obj['extras']['where'])
        self.assertEqual('(SUM(value1) > 5)', query_obj['extras']['having'])

    def test_adhoc_filters_overwrite_legacy_filters(self):
        form_data = {
            'metrics': [{
                'expressionType': 'SIMPLE',
                'aggregate': 'SUM',
                'label': 'SUM(value1)',
                'column': {'column_name': 'value1', 'type': 'DOUBLE'},
            }],
            'adhoc_filters': [
                {
                    'expressionType': 'SIMPLE',
                    'clause': 'WHERE',
                    'subject': 'value2',
                    'operator': '>',
                    'comparator': '100',
                },
                {
                    'expressionType': 'SQL',
                    'clause': 'WHERE',
                    'sqlExpression': 'value3 in (\'North America\')',
                },
            ],
            'having': 'SUM(value1) > 5',
        }
        datasource = self.get_datasource_mock()
        test_viz = viz.TableViz(datasource, form_data)
        query_obj = test_viz.query_obj()
        self.assertEqual(
            [{'col': 'value2', 'val': '100', 'op': '>'}],
            query_obj['filter'],
        )
        self.assertEqual(
            [],
            query_obj['extras']['having_druid'],
        )
        self.assertEqual('(value3 in (\'North America\'))', query_obj['extras']['where'])
        self.assertEqual('', query_obj['extras']['having'])

    @patch('superset.viz.BaseViz.query_obj')
    def test_query_obj_merges_percent_metrics(self, super_query_obj):
        datasource = self.get_datasource_mock()
        form_data = {
            'percent_metrics': ['sum__A', 'avg__B', 'max__Y'],
            'metrics': ['sum__A', 'count', 'avg__C'],
        }
        test_viz = viz.TableViz(datasource, form_data)
        f_query_obj = {
            'metrics': form_data['metrics'],
        }
        super_query_obj.return_value = f_query_obj
        query_obj = test_viz.query_obj()
        self.assertEqual([
            'sum__A', 'count', 'avg__C',
            'avg__B', 'max__Y',
        ], query_obj['metrics'])

    @patch('superset.viz.BaseViz.query_obj')
    def test_query_obj_throws_columns_and_metrics(self, super_query_obj):
        datasource = self.get_datasource_mock()
        form_data = {
            'all_columns': ['A', 'B'],
            'metrics': ['x', 'y'],
        }
        super_query_obj.return_value = {}
        test_viz = viz.TableViz(datasource, form_data)
        with self.assertRaises(Exception):
            test_viz.query_obj()
        del form_data['metrics']
        form_data['groupby'] = ['B', 'C']
        test_viz = viz.TableViz(datasource, form_data)
        with self.assertRaises(Exception):
            test_viz.query_obj()

    @patch('superset.viz.BaseViz.query_obj')
    def test_query_obj_merges_all_columns(self, super_query_obj):
        datasource = self.get_datasource_mock()
        form_data = {
            'all_columns': ['colA', 'colB', 'colC'],
            'order_by_cols': ['["colA", "colB"]', '["colC"]'],
        }
        super_query_obj.return_value = {
            'columns': ['colD', 'colC'],
            'groupby': ['colA', 'colB'],
        }
        test_viz = viz.TableViz(datasource, form_data)
        query_obj = test_viz.query_obj()
        self.assertEqual(form_data['all_columns'], query_obj['columns'])
        self.assertEqual([], query_obj['groupby'])
        self.assertEqual([['colA', 'colB'], ['colC']], query_obj['orderby'])

    @patch('superset.viz.BaseViz.query_obj')
    def test_query_obj_uses_sortby(self, super_query_obj):
        datasource = self.get_datasource_mock()
        form_data = {
            'timeseries_limit_metric': '__time__',
            'order_desc': False,
        }
        super_query_obj.return_value = {
            'metrics': ['colA', 'colB'],
        }
        test_viz = viz.TableViz(datasource, form_data)
        query_obj = test_viz.query_obj()
        self.assertEqual([
            'colA', 'colB', '__time__',
        ], query_obj['metrics'])
        self.assertEqual([(
            '__time__', True,
        )], query_obj['orderby'])

    def test_should_be_timeseries_raises_when_no_granularity(self):
        datasource = self.get_datasource_mock()
        form_data = {'include_time': True}
        test_viz = viz.TableViz(datasource, form_data)
        with self.assertRaises(Exception):
            test_viz.should_be_timeseries()


class PairedTTestTestCase(SupersetTestCase):
    def test_get_data_transforms_dataframe(self):
        form_data = {
            'groupby': ['groupA', 'groupB', 'groupC'],
            'metrics': ['metric1', 'metric2', 'metric3'],
        }
        datasource = self.get_datasource_mock()
        # Test data
        raw = {}
        raw[DTTM_ALIAS] = [100, 200, 300, 100, 200, 300, 100, 200, 300]
        raw['groupA'] = ['a1', 'a1', 'a1', 'b1', 'b1', 'b1', 'c1', 'c1', 'c1']
        raw['groupB'] = ['a2', 'a2', 'a2', 'b2', 'b2', 'b2', 'c2', 'c2', 'c2']
        raw['groupC'] = ['a3', 'a3', 'a3', 'b3', 'b3', 'b3', 'c3', 'c3', 'c3']
        raw['metric1'] = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        raw['metric2'] = [10, 20, 30, 40, 50, 60, 70, 80, 90]
        raw['metric3'] = [100, 200, 300, 400, 500, 600, 700, 800, 900]
        df = pd.DataFrame(raw)
        pairedTTestViz = viz.viz_types['paired_ttest'](datasource, form_data)
        data = pairedTTestViz.get_data(df)
        # Check method correctly transforms data
        expected = {
            'metric1': [
                {
                    'values': [
                        {'x': 100, 'y': 1},
                        {'x': 200, 'y': 2},
                        {'x': 300, 'y': 3}],
                    'group': ('a1', 'a2', 'a3'),
                },
                {
                    'values': [
                        {'x': 100, 'y': 4},
                        {'x': 200, 'y': 5},
                        {'x': 300, 'y': 6}],
                    'group': ('b1', 'b2', 'b3'),
                },
                {
                    'values': [
                        {'x': 100, 'y': 7},
                        {'x': 200, 'y': 8},
                        {'x': 300, 'y': 9}],
                    'group': ('c1', 'c2', 'c3'),
                },
            ],
            'metric2': [
                {
                    'values': [
                        {'x': 100, 'y': 10},
                        {'x': 200, 'y': 20},
                        {'x': 300, 'y': 30}],
                    'group': ('a1', 'a2', 'a3'),
                },
                {
                    'values': [
                        {'x': 100, 'y': 40},
                        {'x': 200, 'y': 50},
                        {'x': 300, 'y': 60}],
                    'group': ('b1', 'b2', 'b3'),
                },
                {
                    'values': [
                        {'x': 100, 'y': 70},
                        {'x': 200, 'y': 80},
                        {'x': 300, 'y': 90}],
                    'group': ('c1', 'c2', 'c3'),
                },
            ],
            'metric3': [
                {
                    'values': [
                        {'x': 100, 'y': 100},
                        {'x': 200, 'y': 200},
                        {'x': 300, 'y': 300}],
                    'group': ('a1', 'a2', 'a3'),
                },
                {
                    'values': [
                        {'x': 100, 'y': 400},
                        {'x': 200, 'y': 500},
                        {'x': 300, 'y': 600}],
                    'group': ('b1', 'b2', 'b3'),
                },
                {
                    'values': [
                        {'x': 100, 'y': 700},
                        {'x': 200, 'y': 800},
                        {'x': 300, 'y': 900}],
                    'group': ('c1', 'c2', 'c3'),
                },
            ],
        }
        self.assertEqual(data, expected)

    def test_get_data_empty_null_keys(self):
        form_data = {
            'groupby': [],
            'metrics': ['', None],
        }
        datasource = self.get_datasource_mock()
        # Test data
        raw = {}
        raw[DTTM_ALIAS] = [100, 200, 300]
        raw[''] = [1, 2, 3]
        raw[None] = [10, 20, 30]

        df = pd.DataFrame(raw)
        pairedTTestViz = viz.viz_types['paired_ttest'](datasource, form_data)
        data = pairedTTestViz.get_data(df)
        # Check method correctly transforms data
        expected = {
            'N/A': [
                {
                    'values': [
                        {'x': 100, 'y': 1},
                        {'x': 200, 'y': 2},
                        {'x': 300, 'y': 3}],
                    'group': 'All',
                },
            ],
            'NULL': [
                {
                    'values': [
                        {'x': 100, 'y': 10},
                        {'x': 200, 'y': 20},
                        {'x': 300, 'y': 30}],
                    'group': 'All',
                },
            ],
        }
        self.assertEqual(data, expected)


class PartitionVizTestCase(SupersetTestCase):

    @patch('superset.viz.BaseViz.query_obj')
    def test_query_obj_time_series_option(self, super_query_obj):
        datasource = self.get_datasource_mock()
        form_data = {}
        test_viz = viz.PartitionViz(datasource, form_data)
        super_query_obj.return_value = {}
        query_obj = test_viz.query_obj()
        self.assertFalse(query_obj['is_timeseries'])
        test_viz.form_data['time_series_option'] = 'agg_sum'
        query_obj = test_viz.query_obj()
        self.assertTrue(query_obj['is_timeseries'])

    def test_levels_for_computes_levels(self):
        raw = {}
        raw[DTTM_ALIAS] = [100, 200, 300, 100, 200, 300, 100, 200, 300]
        raw['groupA'] = ['a1', 'a1', 'a1', 'b1', 'b1', 'b1', 'c1', 'c1', 'c1']
        raw['groupB'] = ['a2', 'a2', 'a2', 'b2', 'b2', 'b2', 'c2', 'c2', 'c2']
        raw['groupC'] = ['a3', 'a3', 'a3', 'b3', 'b3', 'b3', 'c3', 'c3', 'c3']
        raw['metric1'] = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        raw['metric2'] = [10, 20, 30, 40, 50, 60, 70, 80, 90]
        raw['metric3'] = [100, 200, 300, 400, 500, 600, 700, 800, 900]
        df = pd.DataFrame(raw)
        groups = ['groupA', 'groupB', 'groupC']
        time_op = 'agg_sum'
        test_viz = viz.PartitionViz(Mock(), {})
        levels = test_viz.levels_for(time_op, groups, df)
        self.assertEqual(4, len(levels))
        expected = {
            DTTM_ALIAS: 1800,
            'metric1': 45,
            'metric2': 450,
            'metric3': 4500,
        }
        self.assertEqual(expected, levels[0].to_dict())
        expected = {
            DTTM_ALIAS: {'a1': 600, 'b1': 600, 'c1': 600},
            'metric1': {'a1': 6, 'b1': 15, 'c1': 24},
            'metric2': {'a1': 60, 'b1': 150, 'c1': 240},
            'metric3': {'a1': 600, 'b1': 1500, 'c1': 2400},
        }
        self.assertEqual(expected, levels[1].to_dict())
        self.assertEqual(['groupA', 'groupB'], levels[2].index.names)
        self.assertEqual(
            ['groupA', 'groupB', 'groupC'],
            levels[3].index.names,
        )
        time_op = 'agg_mean'
        levels = test_viz.levels_for(time_op, groups, df)
        self.assertEqual(4, len(levels))
        expected = {
            DTTM_ALIAS: 200.0,
            'metric1': 5.0,
            'metric2': 50.0,
            'metric3': 500.0,
        }
        self.assertEqual(expected, levels[0].to_dict())
        expected = {
            DTTM_ALIAS: {'a1': 200, 'c1': 200, 'b1': 200},
            'metric1': {'a1': 2, 'b1': 5, 'c1': 8},
            'metric2': {'a1': 20, 'b1': 50, 'c1': 80},
            'metric3': {'a1': 200, 'b1': 500, 'c1': 800},
        }
        self.assertEqual(expected, levels[1].to_dict())
        self.assertEqual(['groupA', 'groupB'], levels[2].index.names)
        self.assertEqual(
            ['groupA', 'groupB', 'groupC'],
            levels[3].index.names,
        )

    def test_levels_for_diff_computes_difference(self):
        raw = {}
        raw[DTTM_ALIAS] = [100, 200, 300, 100, 200, 300, 100, 200, 300]
        raw['groupA'] = ['a1', 'a1', 'a1', 'b1', 'b1', 'b1', 'c1', 'c1', 'c1']
        raw['groupB'] = ['a2', 'a2', 'a2', 'b2', 'b2', 'b2', 'c2', 'c2', 'c2']
        raw['groupC'] = ['a3', 'a3', 'a3', 'b3', 'b3', 'b3', 'c3', 'c3', 'c3']
        raw['metric1'] = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        raw['metric2'] = [10, 20, 30, 40, 50, 60, 70, 80, 90]
        raw['metric3'] = [100, 200, 300, 400, 500, 600, 700, 800, 900]
        df = pd.DataFrame(raw)
        groups = ['groupA', 'groupB', 'groupC']
        test_viz = viz.PartitionViz(Mock(), {})
        time_op = 'point_diff'
        levels = test_viz.levels_for_diff(time_op, groups, df)
        expected = {
            'metric1': 6,
            'metric2': 60,
            'metric3': 600,
        }
        self.assertEqual(expected, levels[0].to_dict())
        expected = {
            'metric1': {'a1': 2, 'b1': 2, 'c1': 2},
            'metric2': {'a1': 20, 'b1': 20, 'c1': 20},
            'metric3': {'a1': 200, 'b1': 200, 'c1': 200},
        }
        self.assertEqual(expected, levels[1].to_dict())
        self.assertEqual(4, len(levels))
        self.assertEqual(['groupA', 'groupB', 'groupC'], levels[3].index.names)

    def test_levels_for_time_calls_process_data_and_drops_cols(self):
        raw = {}
        raw[DTTM_ALIAS] = [100, 200, 300, 100, 200, 300, 100, 200, 300]
        raw['groupA'] = ['a1', 'a1', 'a1', 'b1', 'b1', 'b1', 'c1', 'c1', 'c1']
        raw['groupB'] = ['a2', 'a2', 'a2', 'b2', 'b2', 'b2', 'c2', 'c2', 'c2']
        raw['groupC'] = ['a3', 'a3', 'a3', 'b3', 'b3', 'b3', 'c3', 'c3', 'c3']
        raw['metric1'] = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        raw['metric2'] = [10, 20, 30, 40, 50, 60, 70, 80, 90]
        raw['metric3'] = [100, 200, 300, 400, 500, 600, 700, 800, 900]
        df = pd.DataFrame(raw)
        groups = ['groupA', 'groupB', 'groupC']
        test_viz = viz.PartitionViz(Mock(), {'groupby': groups})

        def return_args(df_drop, aggregate):
            return df_drop
        test_viz.process_data = Mock(side_effect=return_args)
        levels = test_viz.levels_for_time(groups, df)
        self.assertEqual(4, len(levels))
        cols = [DTTM_ALIAS, 'metric1', 'metric2', 'metric3']
        self.assertEqual(sorted(cols), sorted(levels[0].columns.tolist()))
        cols += ['groupA']
        self.assertEqual(sorted(cols), sorted(levels[1].columns.tolist()))
        cols += ['groupB']
        self.assertEqual(sorted(cols), sorted(levels[2].columns.tolist()))
        cols += ['groupC']
        self.assertEqual(sorted(cols), sorted(levels[3].columns.tolist()))
        self.assertEqual(4, len(test_viz.process_data.mock_calls))

    def test_nest_values_returns_hierarchy(self):
        raw = {}
        raw['groupA'] = ['a1', 'a1', 'a1', 'b1', 'b1', 'b1', 'c1', 'c1', 'c1']
        raw['groupB'] = ['a2', 'a2', 'a2', 'b2', 'b2', 'b2', 'c2', 'c2', 'c2']
        raw['groupC'] = ['a3', 'a3', 'a3', 'b3', 'b3', 'b3', 'c3', 'c3', 'c3']
        raw['metric1'] = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        raw['metric2'] = [10, 20, 30, 40, 50, 60, 70, 80, 90]
        raw['metric3'] = [100, 200, 300, 400, 500, 600, 700, 800, 900]
        df = pd.DataFrame(raw)
        test_viz = viz.PartitionViz(Mock(), {})
        groups = ['groupA', 'groupB', 'groupC']
        levels = test_viz.levels_for('agg_sum', groups, df)
        nest = test_viz.nest_values(levels)
        self.assertEqual(3, len(nest))
        for i in range(0, 3):
            self.assertEqual('metric' + str(i + 1), nest[i]['name'])
        self.assertEqual(3, len(nest[0]['children']))
        self.assertEqual(1, len(nest[0]['children'][0]['children']))
        self.assertEqual(1, len(nest[0]['children'][0]['children'][0]['children']))

    def test_nest_procs_returns_hierarchy(self):
        raw = {}
        raw[DTTM_ALIAS] = [100, 200, 300, 100, 200, 300, 100, 200, 300]
        raw['groupA'] = ['a1', 'a1', 'a1', 'b1', 'b1', 'b1', 'c1', 'c1', 'c1']
        raw['groupB'] = ['a2', 'a2', 'a2', 'b2', 'b2', 'b2', 'c2', 'c2', 'c2']
        raw['groupC'] = ['a3', 'a3', 'a3', 'b3', 'b3', 'b3', 'c3', 'c3', 'c3']
        raw['metric1'] = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        raw['metric2'] = [10, 20, 30, 40, 50, 60, 70, 80, 90]
        raw['metric3'] = [100, 200, 300, 400, 500, 600, 700, 800, 900]
        df = pd.DataFrame(raw)
        test_viz = viz.PartitionViz(Mock(), {})
        groups = ['groupA', 'groupB', 'groupC']
        metrics = ['metric1', 'metric2', 'metric3']
        procs = {}
        for i in range(0, 4):
            df_drop = df.drop(groups[i:], 1)
            pivot = df_drop.pivot_table(
                index=DTTM_ALIAS,
                columns=groups[:i],
                values=metrics,
            )
            procs[i] = pivot
        nest = test_viz.nest_procs(procs)
        self.assertEqual(3, len(nest))
        for i in range(0, 3):
            self.assertEqual('metric' + str(i + 1), nest[i]['name'])
            self.assertEqual(None, nest[i].get('val'))
        self.assertEqual(3, len(nest[0]['children']))
        self.assertEqual(3, len(nest[0]['children'][0]['children']))
        self.assertEqual(1, len(nest[0]['children'][0]['children'][0]['children']))
        self.assertEqual(
            1,
            len(nest[0]['children']
                [0]['children']
                [0]['children']
                [0]['children']),
        )

    def test_get_data_calls_correct_method(self):
        test_viz = viz.PartitionViz(Mock(), {})
        df = Mock()
        with self.assertRaises(ValueError):
            test_viz.get_data(df)
        test_viz.levels_for = Mock(return_value=1)
        test_viz.nest_values = Mock(return_value=1)
        test_viz.form_data['groupby'] = ['groups']
        test_viz.form_data['time_series_option'] = 'not_time'
        test_viz.get_data(df)
        self.assertEqual('agg_sum', test_viz.levels_for.mock_calls[0][1][0])
        test_viz.form_data['time_series_option'] = 'agg_sum'
        test_viz.get_data(df)
        self.assertEqual('agg_sum', test_viz.levels_for.mock_calls[1][1][0])
        test_viz.form_data['time_series_option'] = 'agg_mean'
        test_viz.get_data(df)
        self.assertEqual('agg_mean', test_viz.levels_for.mock_calls[2][1][0])
        test_viz.form_data['time_series_option'] = 'point_diff'
        test_viz.levels_for_diff = Mock(return_value=1)
        test_viz.get_data(df)
        self.assertEqual('point_diff', test_viz.levels_for_diff.mock_calls[0][1][0])
        test_viz.form_data['time_series_option'] = 'point_percent'
        test_viz.get_data(df)
        self.assertEqual('point_percent', test_viz.levels_for_diff.mock_calls[1][1][0])
        test_viz.form_data['time_series_option'] = 'point_factor'
        test_viz.get_data(df)
        self.assertEqual('point_factor', test_viz.levels_for_diff.mock_calls[2][1][0])
        test_viz.levels_for_time = Mock(return_value=1)
        test_viz.nest_procs = Mock(return_value=1)
        test_viz.form_data['time_series_option'] = 'adv_anal'
        test_viz.get_data(df)
        self.assertEqual(1, len(test_viz.levels_for_time.mock_calls))
        self.assertEqual(1, len(test_viz.nest_procs.mock_calls))
        test_viz.form_data['time_series_option'] = 'time_series'
        test_viz.get_data(df)
        self.assertEqual('agg_sum', test_viz.levels_for.mock_calls[3][1][0])
        self.assertEqual(7, len(test_viz.nest_values.mock_calls))


class RoseVisTestCase(SupersetTestCase):

    def test_rose_vis_get_data(self):
        raw = {}
        t1 = pd.Timestamp('2000')
        t2 = pd.Timestamp('2002')
        t3 = pd.Timestamp('2004')
        raw[DTTM_ALIAS] = [t1, t2, t3, t1, t2, t3, t1, t2, t3]
        raw['groupA'] = ['a1', 'a1', 'a1', 'b1', 'b1', 'b1', 'c1', 'c1', 'c1']
        raw['groupB'] = ['a2', 'a2', 'a2', 'b2', 'b2', 'b2', 'c2', 'c2', 'c2']
        raw['groupC'] = ['a3', 'a3', 'a3', 'b3', 'b3', 'b3', 'c3', 'c3', 'c3']
        raw['metric1'] = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        df = pd.DataFrame(raw)
        fd = {
            'metrics': ['metric1'],
            'groupby': ['groupA'],
        }
        test_viz = viz.RoseViz(Mock(), fd)
        test_viz.metrics = fd['metrics']
        res = test_viz.get_data(df)
        expected = {
            946684800000000000: [
                {'time': t1, 'value': 1, 'key': ('a1',), 'name': ('a1',)},
                {'time': t1, 'value': 4, 'key': ('b1',), 'name': ('b1',)},
                {'time': t1, 'value': 7, 'key': ('c1',), 'name': ('c1',)},
            ],
            1009843200000000000: [
                {'time': t2, 'value': 2, 'key': ('a1',), 'name': ('a1',)},
                {'time': t2, 'value': 5, 'key': ('b1',), 'name': ('b1',)},
                {'time': t2, 'value': 8, 'key': ('c1',), 'name': ('c1',)},
            ],
            1072915200000000000: [
                {'time': t3, 'value': 3, 'key': ('a1',), 'name': ('a1',)},
                {'time': t3, 'value': 6, 'key': ('b1',), 'name': ('b1',)},
                {'time': t3, 'value': 9, 'key': ('c1',), 'name': ('c1',)},
            ],
        }
        self.assertEqual(expected, res)


class TimeSeriesTableVizTestCase(SupersetTestCase):

    def test_get_data_metrics(self):
        form_data = {
            'metrics': ['sum__A', 'count'],
            'groupby': [],
        }
        datasource = self.get_datasource_mock()
        raw = {}
        t1 = pd.Timestamp('2000')
        t2 = pd.Timestamp('2002')
        raw[DTTM_ALIAS] = [t1, t2]
        raw['sum__A'] = [15, 20]
        raw['count'] = [6, 7]
        df = pd.DataFrame(raw)
        test_viz = viz.TimeTableViz(datasource, form_data)
        data = test_viz.get_data(df)
        # Check method correctly transforms data
        self.assertEqual(set(['count', 'sum__A']), set(data['columns']))
        time_format = '%Y-%m-%d %H:%M:%S'
        expected = {
            t1.strftime(time_format): {
                'sum__A': 15,
                'count': 6,
            },
            t2.strftime(time_format): {
                'sum__A': 20,
                'count': 7,
            },
        }
        self.assertEqual(expected, data['records'])

    def test_get_data_group_by(self):
        form_data = {
            'metrics': ['sum__A'],
            'groupby': ['groupby1'],
        }
        datasource = self.get_datasource_mock()
        raw = {}
        t1 = pd.Timestamp('2000')
        t2 = pd.Timestamp('2002')
        raw[DTTM_ALIAS] = [t1, t1, t1, t2, t2, t2]
        raw['sum__A'] = [15, 20, 25, 30, 35, 40]
        raw['groupby1'] = ['a1', 'a2', 'a3', 'a1', 'a2', 'a3']
        df = pd.DataFrame(raw)
        test_viz = viz.TimeTableViz(datasource, form_data)
        data = test_viz.get_data(df)
        # Check method correctly transforms data
        self.assertEqual(set(['a1', 'a2', 'a3']), set(data['columns']))
        time_format = '%Y-%m-%d %H:%M:%S'
        expected = {
            t1.strftime(time_format): {
                'a1': 15,
                'a2': 20,
                'a3': 25,
            },
            t2.strftime(time_format): {
                'a1': 30,
                'a2': 35,
                'a3': 40,
            },
        }
        self.assertEqual(expected, data['records'])

    @patch('superset.viz.BaseViz.query_obj')
    def test_query_obj_throws_metrics_and_groupby(self, super_query_obj):
        datasource = self.get_datasource_mock()
        form_data = {
            'groupby': ['a'],
        }
        super_query_obj.return_value = {}
        test_viz = viz.TimeTableViz(datasource, form_data)
        with self.assertRaises(Exception):
            test_viz.query_obj()
        form_data['metrics'] = ['x', 'y']
        test_viz = viz.TimeTableViz(datasource, form_data)
        with self.assertRaises(Exception):
            test_viz.query_obj()


class BaseDeckGLVizTestCase(SupersetTestCase):

    def test_get_metrics(self):
        form_data = load_fixture('deck_path_form_data.json')
        datasource = self.get_datasource_mock()
        test_viz_deckgl = viz.BaseDeckGLViz(datasource, form_data)
        result = test_viz_deckgl.get_metrics()
        assert result == [form_data.get('size')]

        form_data = {}
        test_viz_deckgl = viz.BaseDeckGLViz(datasource, form_data)
        result = test_viz_deckgl.get_metrics()
        assert result == []

    def test_scatterviz_get_metrics(self):
        form_data = load_fixture('deck_path_form_data.json')
        datasource = self.get_datasource_mock()

        form_data = {}
        test_viz_deckgl = viz.DeckScatterViz(datasource, form_data)
        test_viz_deckgl.point_radius_fixed = {'type': 'metric', 'value': 'int'}
        result = test_viz_deckgl.get_metrics()
        assert result == ['int']

        form_data = {}
        test_viz_deckgl = viz.DeckScatterViz(datasource, form_data)
        test_viz_deckgl.point_radius_fixed = {}
        result = test_viz_deckgl.get_metrics()
        assert result is None

    def test_get_js_columns(self):
        form_data = load_fixture('deck_path_form_data.json')
        datasource = self.get_datasource_mock()
        mock_d = {
            'a': 'dummy1',
            'b': 'dummy2',
            'c': 'dummy3',
        }
        test_viz_deckgl = viz.BaseDeckGLViz(datasource, form_data)
        result = test_viz_deckgl.get_js_columns(mock_d)

        assert result == {'color': None}

    def test_get_properties(self):
        mock_d = {}
        form_data = load_fixture('deck_path_form_data.json')
        datasource = self.get_datasource_mock()
        test_viz_deckgl = viz.BaseDeckGLViz(datasource, form_data)

        with self.assertRaises(NotImplementedError) as context:
            test_viz_deckgl.get_properties(mock_d)

        self.assertTrue('' in str(context.exception))

    def test_process_spatial_query_obj(self):
        form_data = load_fixture('deck_path_form_data.json')
        datasource = self.get_datasource_mock()
        mock_key = 'spatial_key'
        mock_gb = []
        test_viz_deckgl = viz.BaseDeckGLViz(datasource, form_data)

        with self.assertRaises(ValueError) as context:
            test_viz_deckgl.process_spatial_query_obj(mock_key, mock_gb)

        self.assertTrue('Bad spatial key' in str(context.exception))

        test_form_data = {
            'latlong_key': {
                'type': 'latlong',
                'lonCol': 'lon',
                'latCol': 'lat',
            },
            'delimited_key': {
                'type': 'delimited',
                'lonlatCol': 'lonlat',
            },
            'geohash_key': {
                'type': 'geohash',
                'geohashCol': 'geo',
            },
        }

        datasource = self.get_datasource_mock()
        expected_results = {
            'latlong_key': ['lon', 'lat'],
            'delimited_key': ['lonlat'],
            'geohash_key': ['geo'],
        }
        for mock_key in ['latlong_key', 'delimited_key', 'geohash_key']:
            mock_gb = []
            test_viz_deckgl = viz.BaseDeckGLViz(datasource, test_form_data)
            test_viz_deckgl.process_spatial_query_obj(mock_key, mock_gb)
            assert expected_results.get(mock_key) == mock_gb

    def test_geojson_query_obj(self):
        form_data = load_fixture('deck_geojson_form_data.json')
        datasource = self.get_datasource_mock()
        test_viz_deckgl = viz.DeckGeoJson(datasource, form_data)
        results = test_viz_deckgl.query_obj()

        assert results['metrics'] == []
        assert results['groupby'] == []
        assert results['columns'] == ['test_col']

    def test_parse_coordinates(self):
        form_data = load_fixture('deck_path_form_data.json')
        datasource = self.get_datasource_mock()
        viz_instance = viz.BaseDeckGLViz(datasource, form_data)

        coord = viz_instance.parse_coordinates('1.23, 3.21')
        self.assertEquals(coord, (1.23, 3.21))

        coord = viz_instance.parse_coordinates('1.23 3.21')
        self.assertEquals(coord, (1.23, 3.21))

        self.assertEquals(viz_instance.parse_coordinates(None), None)

        self.assertEquals(viz_instance.parse_coordinates(''), None)

    def test_parse_coordinates_raises(self):
        form_data = load_fixture('deck_path_form_data.json')
        datasource = self.get_datasource_mock()
        test_viz_deckgl = viz.BaseDeckGLViz(datasource, form_data)

        with self.assertRaises(SpatialException):
            test_viz_deckgl.parse_coordinates('NULL')

        with self.assertRaises(SpatialException):
            test_viz_deckgl.parse_coordinates('fldkjsalkj,fdlaskjfjadlksj')

    @patch('superset.utils.core.uuid.uuid4')
    def test_filter_nulls(self, mock_uuid4):
        mock_uuid4.return_value = uuid.UUID('12345678123456781234567812345678')
        test_form_data = {
            'latlong_key': {
                'type': 'latlong',
                'lonCol': 'lon',
                'latCol': 'lat',
            },
            'delimited_key': {
                'type': 'delimited',
                'lonlatCol': 'lonlat',
            },
            'geohash_key': {
                'type': 'geohash',
                'geohashCol': 'geo',
            },
        }

        datasource = self.get_datasource_mock()
        expected_results = {
            'latlong_key': [{
                'clause': 'WHERE',
                'expressionType': 'SIMPLE',
                'filterOptionName': '12345678-1234-5678-1234-567812345678',
                'comparator': '',
                'operator': 'IS NOT NULL',
                'subject': 'lat',
            }, {
                'clause': 'WHERE',
                'expressionType': 'SIMPLE',
                'filterOptionName': '12345678-1234-5678-1234-567812345678',
                'comparator': '',
                'operator': 'IS NOT NULL',
                'subject': 'lon',
            }],
            'delimited_key': [{
                'clause': 'WHERE',
                'expressionType': 'SIMPLE',
                'filterOptionName': '12345678-1234-5678-1234-567812345678',
                'comparator': '',
                'operator': 'IS NOT NULL',
                'subject': 'lonlat',
            }],
            'geohash_key': [{
                'clause': 'WHERE',
                'expressionType': 'SIMPLE',
                'filterOptionName': '12345678-1234-5678-1234-567812345678',
                'comparator': '',
                'operator': 'IS NOT NULL',
                'subject': 'geo',
            }],
        }
        for mock_key in ['latlong_key', 'delimited_key', 'geohash_key']:
            test_viz_deckgl = viz.BaseDeckGLViz(
                datasource, test_form_data.copy())
            test_viz_deckgl.spatial_control_keys = [mock_key]
            test_viz_deckgl.add_null_filters()
            adhoc_filters = test_viz_deckgl.form_data['adhoc_filters']
            assert expected_results.get(mock_key) == adhoc_filters


class TimeSeriesVizTestCase(SupersetTestCase):

    def test_timeseries_unicode_data(self):
        datasource = self.get_datasource_mock()
        form_data = {
            'groupby': ['name'],
            'metrics': ['sum__payout'],
        }
        raw = {}
        raw['name'] = [
            'Real Madrid C.F.????????????????', 'Real Madrid C.F.????????????????',
            'Real Madrid Basket', 'Real Madrid Basket',
        ]
        raw['__timestamp'] = [
            '2018-02-20T00:00:00', '2018-03-09T00:00:00',
            '2018-02-20T00:00:00', '2018-03-09T00:00:00',
        ]
        raw['sum__payout'] = [2, 2, 4, 4]
        df = pd.DataFrame(raw)

        test_viz = viz.NVD3TimeSeriesViz(datasource, form_data)
        viz_data = {}
        viz_data = test_viz.get_data(df)
        expected = [
            {u'values': [
                {u'y': 4, u'x': u'2018-02-20T00:00:00'},
                {u'y': 4, u'x': u'2018-03-09T00:00:00'}],
                u'key': (u'Real Madrid Basket',)},
            {u'values': [
                {u'y': 2, u'x': u'2018-02-20T00:00:00'},
                {u'y': 2, u'x': u'2018-03-09T00:00:00'}],
                u'key': (u'Real Madrid C.F.\U0001f1fa\U0001f1f8\U0001f1ec\U0001f1e7',)},
        ]
        self.assertEqual(expected, viz_data)
