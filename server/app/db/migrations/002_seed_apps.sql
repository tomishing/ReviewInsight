-- Initial target apps (SPEC.md). Runs once; apps deleted later stay deleted.
INSERT INTO apps (name, play_id, appstore_id) VALUES
  ('Monarch Money',            'com.monarchmoney.mobile',           '1459319842'),
  ('YNAB',                     'com.youneedabudget.evergreen.app',  '1010865877'),
  ('Money Manager (Realbyte)', 'com.realbyteapps.moneymanagerfree', '560481810'),
  ('Cashew',                   'com.budget.tracker_app',            '6463662930'),
  ('Yomio',                    'com.yomio.app',                     '6757447181'),
  ('Money Tracker',            'com.freeman.moneymanager',          NULL)
ON CONFLICT DO NOTHING;
