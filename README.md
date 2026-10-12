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

## Emails in local development

Nothing is sent to a real inbox locally. With `EMAIL_URL=filemail://` (the default)
every email is saved as a file in `sent_emails/`, the local test mailbox: open the
newest file to read the message and its verification link. `EMAIL_URL=consolemail://`
prints the email to the server log instead. The website says when an email was only
saved locally.

For real delivery set `EMAIL_URL=smtp://user:password@host:587/?tls=True` and
`DEFAULT_FROM_EMAIL` in `.env` (never commit `.env`). `FRONTEND_URL` is the website
address used in the links.
