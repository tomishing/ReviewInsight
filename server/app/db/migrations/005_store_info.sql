-- Store listing details per app and store (rating, price, in-app purchases, ads); latest only.
CREATE TABLE store_info (
  app_id INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
  store TEXT NOT NULL CHECK (store IN ('play','appstore')),
  data JSONB,  -- app.fetchers.storeinfo.StoreInfo; kept from the last success when a refresh fails
  error TEXT,  -- last refresh error, NULL when it succeeded
  fetched_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (app_id, store)
);
