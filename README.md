[![tests](https://github.com/boutetnico/ansible-role-monitoring/workflows/Test%20ansible%20role/badge.svg)](https://github.com/boutetnico/ansible-role-monitoring/actions?query=workflow%3A%22Test+ansible+role%22)
[![Ansible Galaxy](https://img.shields.io/badge/galaxy-boutetnico.monitoring-blue.svg)](https://galaxy.ansible.com/boutetnico/monitoring)

ansible-role-monitoring
=======================

This role installs host checks that alert to Slack and/or Telegram: failed units, services, log errors, the journal, disk usage, pending security updates and reboots, host posture, backups (S3, B2), WordPress administrators, Laravel failed jobs, MySQL replication, query results, slow queries and fragmentation, Elasticsearch log rules, Sentry intake and a few AWS signals.

Each check is a script in `/usr/local/bin`, enabled by its variable and run on its interval by a dispatcher that a systemd timer starts every minute. A condition alerts once, optionally reminds, and reports its recovery. Slack shows each message as a red, green or grey attachment, for an alert, a recovery or anything else, with the first line as its title.

Requirements
------------

Ansible 2.10 or newer, systemd and Python 3 on the host. Some checks need more:

- AWS checks: `boto3`.
- MySQL checks: root access through `/root/.my.cnf`.
- B2 backups: the `b2` CLI.
- Sentry intake: Docker, for the container report.
- SMS: `openssl`, to sign the Vonage token.

Supported Platforms
-------------------

- [Debian - 12 (Bookworm)](https://wiki.debian.org/DebianBookworm)
- [Debian - 13 (Trixie)](https://wiki.debian.org/DebianTrixie)
- [Ubuntu - 22.04 (Jammy Jellyfish)](http://releases.ubuntu.com/22.04/)
- [Ubuntu - 24.04 (Noble Numbat)](http://releases.ubuntu.com/24.04/)

Role Variables
--------------

| Variable                              | Required | Default                           | Choices | Comments                                                       |
|---------------------------------------|----------|-----------------------------------|---------|----------------------------------------------------------------|
| monitoring_label                      | no       | `""`                              | string  | Prefix of every message, before the hostname.                  |
| monitoring_scripts_path               | yes      | `/usr/local/bin`                  | string  |                                                                |
| monitoring_state_dir                  | yes      | `/var/lib/monitoring`             | string  |                                                                |
| monitoring_slack_webhook_url          | no       | `""`                              | string  | Slack incoming webhook.                                        |
| monitoring_telegram_bot_token         | no       | `""`                              | string  | Telegram needs both the token and the chat id.                 |
| monitoring_telegram_chat_id           | no       | `""`                              | string  |                                                                |
| monitoring_vonage_application_id      | no       | `""`                              | string  | Vonage application with the Messages capability.               |
| monitoring_vonage_private_key         | no       | `""`                              | string  | That application's private key (PEM), signs short-lived JWTs.  |
| monitoring_sms_from                   | no       | `Monitoring`                      | string  | Sender name.                                                   |
| monitoring_sms_to                     | no       | `[]`                              | list    | International format without `+`, e.g. `33612345678`.         |
| monitoring_sms_keys                   | no       | `[]`                              | list    | Alert key regexes that also send an SMS, e.g. `^services-`.    |
| monitoring_reminder_minutes           | yes      | `0`                               | int     | Repeat an ongoing alert this often; 0 alerts once.             |
| monitoring_maintenance_flag           | yes      | `/var/lib/monitoring/maintenance` | string  | While this file exists, nothing is sent.                       |
| monitoring_maintenance_max_minutes    | yes      | `0`                               | int     | A flag older than this is ignored; 0 never expires.            |
| monitoring_intervals                  | no       | `{}`                              | dict    | Check name to interval in minutes, overriding the default.     |
| monitoring_custom_checks              | no       | `[]`                              | list    | `name`, `src` (template), `every` (minutes).                   |
| monitoring_systemd_failures_enabled   | yes      | `true`                            | bool    | Every minute.                                                  |
| monitoring_systemd_failures_ignore    | no       | `[]`                              | list    | Unit name regexes.                                             |
| monitoring_service_checks             | no       | `[]`                              | list    | Every minute, see below.                                       |
| monitoring_file_checks                | no       | `[]`                              | list    | Daily; `path`, optional `max_age_days`.                        |
| monitoring_disk_usage_enabled         | yes      | `true`                            | bool    | Every 5 minutes.                                               |
| monitoring_disk_usage_threshold       | yes      | `85`                              | int     | Percent.                                                       |
| monitoring_disk_usage_excludes        | no       | `[]`                              | list    | Mount point prefixes.                                          |
| monitoring_apt_security_enabled       | yes      | `true`                            | bool    | Daily; inert unless `unattended_package_blacklist` is defined. |
| monitoring_reboot_required_enabled    | yes      | `true`                            | bool    | Daily.                                                         |
| monitoring_logfile_checks             | no       | `[]`                              | list    | Every 5 minutes, see below.                                    |
| monitoring_journal_watch              | no       | `{}`                              | dict    | Every minute; `ignore` (list of regexes).                      |
| monitoring_wp_admins_checks           | no       | `[]`                              | list    | `name`, `database`, `table_prefix`, `multisite`.               |
| monitoring_failed_jobs_checks         | no       | `[]`                              | list    | `name`, `database`, `table`, `window_days`.                    |
| monitoring_horizon_failed_jobs_checks | no       | `[]`                              | list    | `name`, `redis_host`, `redis_port`, `redis_db`, `prefix`.      |
| monitoring_mysql_query_checks         | no       | `[]`                              | list    | Every 5 minutes; `name`, `query`, `min` and/or `max`.          |
| monitoring_posture_watch              | no       | `{}`                              | dict    | Hourly; `listeners`, `container_restarts`, `php_ini`.          |
| monitoring_ip_pool_watch              | no       | `{}`                              | dict    | `interface`, `ipv4`, `ipv6` (expected counts).                 |
| monitoring_b2_backup_watch            | no       | `{}`                              | dict    | Hourly; `bucket`, `folders`, `max_age_hours`, `env`.           |
| monitoring_s3_backup_watch            | no       | `{}`                              | dict    | `region`, `credentials`, `checks`, see below.                  |
| monitoring_cpu_credits_watch          | no       | `{}`                              | dict    | `region`, `credentials`, `tag_key`, `tag_value`.               |
| monitoring_alb_targets_watch          | no       | `{}`                              | dict    | `region`, `credentials`, `tag_key`, `tag_value`.               |
| monitoring_ses_quota_watch            | no       | `{}`                              | dict    | `region`, `credentials`, `threshold_percent`.                  |
| monitoring_sentry_events_watch        | no       | `{}`                              | dict    | `api_url`, `api_token`, `compose_project`.                     |
| monitoring_es_logs_watch              | no       | `{}`                              | dict    | `url`, `username`, `password`, `timeout`, `rules`.             |
| monitoring_slow_query_watch           | no       | `{}`                              | dict    | `slow_log_path` and thresholds.                                |
| monitoring_mysql_replication_watch    | no       | `{}`                              | dict    | Every minute; `max_lag_seconds` (default 7200).                |
| monitoring_table_fragmentation_watch  | no       | `{}`                              | dict    | Daily; `min_free_mb`, `min_free_pct`.                          |

A check whose variable is empty or false is not installed.

Each `monitoring_service_checks` entry takes `name`, optional `retries` (5 seconds apart) and one of `unit` (systemd unit), `port` (with optional `host`), `socket`, or `url` with optional `status` (default 200), `resolve` (IP to connect to instead of DNS), `host_header`, `https_forwarded`, `username`/`password`, `headers` (dict, sent on stdin with the credentials so neither shows in the process list), `max_time` and `validate_certs`.

Each `monitoring_logfile_checks` entry takes `name`, `path`, `pattern` (ERE) and optionally `exclude` (ERE), `context` (lines after each match), `ignore_case` (default true), `min_matches` (default 1), `entry_start` (ERE marking the first line of a multi-line entry) and `glob` (pick the newest file matching `path`). Only lines written since the previous run are read; rotation to `<path>.1` is followed.

A `monitoring_mysql_query_checks` query must return one number, e.g. `SELECT COUNT(*) FROM mysql.time_zone_name` with `min: 1`; it alerts below `min`, above `max`, or when the query fails.

AWS checks take `credentials`: `default` (the boto3 credential chain) or `instance-profile` (EC2 instance metadata only). Each `monitoring_s3_backup_watch.checks` entry takes `bucket`, `prefix`, `max_age_hours` and optionally `min_size` (bytes) and `name`.

Elasticsearch `rules` are `frequency` rules (`filter`, `threshold`, `realert_minutes`) or `flatline` rules (`threshold`, `baseline_hours`), each with `name`, `title`, `index`, `timeframe_minutes`, `query_key`, `text_template` and optionally `timestamp_field` (default `@timestamp`). `timeout` is how long a query may take, in seconds (default 10).

Dependencies
------------

None

Example Playbook
----------------

    - hosts: all
      roles:
        - role: ansible-role-monitoring
          monitoring_label: myapp
          monitoring_telegram_bot_token: "{{ vault_telegram_bot_token }}"
          monitoring_telegram_chat_id: "123456789"
          monitoring_reminder_minutes: 30
          monitoring_service_checks:
            - name: nginx
              unit: nginx
              retries: 6
            - name: app
              url: https://example.com/up
              resolve: 127.0.0.1
          monitoring_logfile_checks:
            - name: nginx
              path: /var/log/nginx/error.log
              pattern: "\\[(error|crit|alert|emerg)\\]"
              entry_start: "^[0-9]+/[0-9]+/[0-9]+ "
          monitoring_posture_watch:
            listeners:
              - 0.0.0.0:22
              - 0.0.0.0:443

Usage
-----

`monitoring-notify test` sends a test message. `monitoring-notify alert|clear KEY MESSAGE`, `resolve PREFIX [KEY...]` and `send MESSAGE` are what the checks call, and what custom checks should call too. An alert whose key matches `monitoring_sms_keys` also sends an SMS when raised and when cleared; `monitoring-notify sms TEXT NUMBER...` sends one directly. SMS go through the Vonage Messages API, authenticated with a JWT signed by the application's private key, so the account API secret never reaches the host.

Some alerts carry host data to Slack or Telegram: `wp-admins` lists administrator logins and emails, and `logfiles`, `journal` and `es-logs` forward the matching log lines.

Before planned work, `touch /var/lib/monitoring/maintenance`, and remove it when done.

Testing
-------

    molecule test

License
-------

MIT

Author Information
------------------

[@boutetnico](https://github.com/boutetnico)
