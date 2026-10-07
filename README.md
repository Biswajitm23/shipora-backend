# Shipora backend

Shipora logistics platform: the API the Shipora website talks to.
The website lives in [shipora-frontend](https://github.com/Biswajitm23/shipora-frontend).

## Local setup

```
sudo -u postgres psql -c "CREATE USER shipora WITH PASSWORD 'postgres' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE shipora OWNER shipora;"
cp .env.example .env
make install migrate
make run            # http://localhost:8000/api/
make test           # make test ARGS=apps/accounts for one app
```

Emails are printed to the server log by default (`EMAIL_URL=consolemail://`).
