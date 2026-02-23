import unittest
from app import app
from unittest.mock import patch
import pandas as pd

class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_index_route(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'A\xe8\x82\xa1\xe5\x8e\x86\xe5\x8f\xb2\xe6\x95\xb0\xe6\x8d\xae\xe8\x8e\xb7\xe5\x8f\x96', response.data) # "A股历史数据获取" in bytes

    @patch('app.fetch_stock_data')
    def test_fetch_route_success(self, mock_fetch):
        # Mock the data_loader response
        mock_df = pd.DataFrame({
            'date': ['2023-01-01'],
            'open': [100],
            'high': [110],
            'low': [90],
            'close': [105],
            'volume': [1000]
        })
        mock_fetch.return_value = mock_df

        response = self.app.post('/fetch', data={
            'symbol': '600519',
            'start_date': '20230101',
            'end_date': '20230102'
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['open'], 100)

    def test_fetch_route_missing_fields(self):
        response = self.app.post('/fetch', data={
            'symbol': '600519'
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Missing required fields', response.data)

    @patch('app.fetch_stock_data')
    def test_fetch_route_error(self, mock_fetch):
        mock_fetch.side_effect = Exception("Test Error")

        response = self.app.post('/fetch', data={
            'symbol': '600519',
            'start_date': '20230101',
            'end_date': '20230102'
        })

        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Test Error', response.data)

if __name__ == '__main__':
    unittest.main()
