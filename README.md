[![tests](https://github.com/boutetnico/ansible-role-monitoring/workflows/Test%20ansible%20role/badge.svg)](https://github.com/boutetnico/ansible-role-monitoring/actions?query=workflow%3A%22Test+ansible+role%22)
[![Ansible Galaxy](https://img.shields.io/badge/galaxy-boutetnico.monitoring-blue.svg)](https://galaxy.ansible.com/boutetnico/monitoring)

ansible-role-monitoring
=======================

Host checks that alert to Slack, Telegram and SMS, with no agent or server to run.

- Each check is a script in `/usr/local/bin`, installed only when its variable is set.
- A systemd timer starts a dispatcher every minute, which runs each check on its own interval.
- A problem alerts once (optionally with reminders) and reports its recovery.
- Slack shows alerts in red, recoveries in green and everything else in grey.

Requirements
------------

Ansible 2.10 or newer, systemd and Python 3 on the host. Some checks need more:

| For           | You need                         |
|---------------|----------------------------------|
| AWS checks    | `boto3`                          |
| MySQL checks  | root access via `/root/.my.cnf`  |
| B2 backups    | the `b2` CLI                     |
| Sentry intake | Docker, for the container report |
| SMS           | `openssl`, to sign Vonage tokens |

Supported Platforms
-------------------

- [Debian - 12 (Bookworm)](https://wiki.debian.org/DebianBookworm)
- [Debian - 13 (Trixie)](https://wiki.debian.org/DebianTrixie)
- [Ubuntu - 22.04 (Jammy Jellyfish)](http://releases.ubuntu.com/22.04/)
- [Ubuntu - 24.04 (Noble Numbat)](http://releases.ubuntu.com/24.04/)

Example Playbook
----------------

With only a webhook, you get failed units, disk usage, security updates and pending reboots. Add checks as you need them:

    - hosts: all
      roles:
        - role: ansible-role-monitoring
          monitoring_slack_webhook_url: "{{ vault_slack_webhook_url }}"
          monitoring_service_checks:
            - name: nginx
              unit: nginx
            - name: app
              url: https://example.com/up
              resolve: 127.0.0.1
          monitoring_logfile_checks:
            - name: nginx
              path: /var/log/nginx/error.log
              pattern: "\\[(error|crit|alert|emerg)\\]"

Then check delivery with `monitoring-notify test`.

Checks
------

| Check                 | Enabled by                              | Every  | Alerts when                                                  |
|-----------------------|-----------------------------------------|--------|--------------------------------------------------------------|
| `systemd-failures`    | `monitoring_systemd_failures_enabled` ✓ | 1 min  | a systemd unit has failed                                    |
| `disk-usage`          | `monitoring_disk_usage_enabled` ✓       | 5 min  | a filesystem is fuller than the threshold                    |
| `apt-security`        | `monitoring_apt_security_enabled` ✓     | daily  | security updates are pending                                 |
| `reboot-required`     | `monitoring_reboot_required_enabled` ✓  | daily  | the host needs a reboot                                      |
| `services`            | `monitoring_service_checks`             | 1 min  | a unit, port, socket or URL is down                          |
| `journal`             | `monitoring_journal_watch`              | 1 min  | the journal gets entries of priority err or worse            |
| `logfiles`            | `monitoring_logfile_checks`             | 5 min  | new lines in a log file match a pattern                      |
| `es-logs`             | `monitoring_es_logs_watch`              | 1 min  | an Elasticsearch log rule matches, or a source goes quiet    |
| `files`               | `monitoring_file_checks`                | daily  | a file is missing or too old                                 |
| `posture`             | `monitoring_posture_watch`              | hourly | unexpected listeners, restart loops, drifted PHP settings    |
| `ip-pool`             | `monitoring_ip_pool_watch`              | 1 min  | an interface holds fewer addresses than expected             |
| `mysql-replication`   | `monitoring_mysql_replication_watch`    | 1 min  | replica threads stop, or lag passes the limit                |
| `mysql-queries`       | `monitoring_mysql_query_checks`         | 5 min  | a query's number leaves its min/max, or the query fails      |
| `slow-queries`        | `monitoring_slow_query_watch`           | 5 min  | a new query fingerprint is slow or scans many rows           |
| `table-fragmentation` | `monitoring_table_fragmentation_watch`  | daily  | an InnoDB table holds enough free space to optimize          |
| `wp-admins`           | `monitoring_wp_admins_checks`           | 5 min  | a WordPress site gains administrators                        |
| `failed-jobs`         | `monitoring_failed_jobs_checks`         | 5 min  | a Laravel `failed_jobs` table gains rows                     |
| `horizon-failed-jobs` | `monitoring_horizon_failed_jobs_checks` | 1 min  | Horizon's failed job count grows                             |
| `sentry-events`       | `monitoring_sentry_events_watch`        | 5 min  | a self-hosted Sentry accepted no event                       |
| `b2-backups`          | `monitoring_b2_backup_watch`            | hourly | the newest backup in a B2 folder is missing or too old       |
| `s3-backups`          | `monitoring_s3_backup_watch`            | 5 min  | the newest backup under an S3 prefix is too old or too small |
| `alb-targets`         | `monitoring_alb_targets_watch`          | 1 min  | a load balancer target stays unhealthy                       |
| `cpu-credits`         | `monitoring_cpu_credits_watch`          | 5 min  | a burstable EC2 instance drains its CPU credits              |
| `ses-quota`           | `monitoring_ses_quota_watch`            | 5 min  | SES sends pass a share of the 24-hour quota                  |

✓ on by default. Change an interval with `monitoring_intervals`, e.g. `{disk-usage: 15}`.

Role Variables
--------------

### Notifications

| Variable                             | Default                           | Comments                                                    |
|--------------------------------------|-----------------------------------|-------------------------------------------------------------|
| `monitoring_slack_webhook_url`       | `""`                              | Slack incoming webhook.                                     |
| `monitoring_telegram_bot_token`      | `""`                              | Telegram needs both the token and the chat id.              |
| `monitoring_telegram_chat_id`        | `""`                              |                                                             |
| `monitoring_label`                   | `""`                              | Prefix of every message, e.g. the environment.              |
| `monitoring_reminder_minutes`        | `0`                               | Repeat an ongoing alert this often; 0 alerts once.          |
| `monitoring_vonage_application_id`   | `""`                              | Vonage application with the Messages capability.            |
| `monitoring_vonage_private_key`      | `""`                              | Its private key (PEM), used to sign short-lived JWTs.       |
| `monitoring_sms_from`                | `Monitoring`                      | SMS sender name.                                            |
| `monitoring_sms_to`                  | `[]`                              | Numbers in international format without `+`.                |
| `monitoring_sms_keys`                | `[]`                              | Alert key regexes that also send an SMS, e.g. `^services-`. |
| `monitoring_maintenance_flag`        | `/var/lib/monitoring/maintenance` | While this file exists, nothing is sent.                    |
| `monitoring_maintenance_max_minutes` | `0`                               | Ignore a flag older than this; 0 never expires.             |

### General

| Variable                   | Default               | Comments                                              |
|----------------------------|-----------------------|-------------------------------------------------------|
| `monitoring_scripts_path`  | `/usr/local/bin`      |                                                       |
| `monitoring_state_dir`     | `/var/lib/monitoring` | Alert state, one file per active alert.               |
| `monitoring_intervals`     | `{}`                  | Check name to interval in minutes.                    |
| `monitoring_custom_checks` | `[]`                  | Your own checks, see [Custom checks](#custom-checks). |

### Check settings

Where a key has a default, the example shows it. Names, paths, buckets and credentials are examples.

**System**

    monitoring_systemd_failures_ignore: []     # unit name regexes
    monitoring_disk_usage_threshold: 85        # percent
    monitoring_disk_usage_excludes: []         # mount point prefixes
    monitoring_journal_watch:
      ignore: []                               # regexes
    monitoring_file_checks:
      - path: /var/backups/db.sql.gz
        max_age_days: 1                        # optional
    monitoring_posture_watch:
      listeners: [0.0.0.0:22, 0.0.0.0:443]     # expected TCP listeners
      container_restarts: 3                    # restarts per run that alert
      php_ini: {expose_php: ""}                # expected php-fpm values
    monitoring_ip_pool_watch:
      interface: eth0
      ipv4: 1                                  # expected address counts
      ipv6: 1

`apt-security` stays silent unless `unattended_package_blacklist` is defined.

**Services**: each entry has a `name`, optional `retries` (5 seconds apart) and one target:

    monitoring_service_checks:
      - {name: nginx, unit: nginx}
      - {name: redis, port: 6379}       # host defaults to 127.0.0.1
      - {name: php, socket: /run/php/php-fpm.sock}
      - name: app
        url: https://example.com/up
        status: 200                  # expected status
        resolve: 127.0.0.1           # connect here instead of DNS
        host_header: example.com
        https_forwarded: false       # send X-Forwarded-Proto: https
        username: ""                 # basic auth
        password: ""
        headers: {}                  # sent on stdin, never in the process list
        max_time: 5                  # seconds
        validate_certs: true

**Log files**: only lines written since the previous run are read, following rotation to `<path>.1`.

    monitoring_logfile_checks:
      - name: nginx
        path: /var/log/nginx/error.log
        pattern: "\\[(error|crit)\\]"   # ERE
        exclude: ""                     # ERE
        context: 0                      # lines kept after each match
        ignore_case: true
        min_matches: 1
        entry_start: ""                 # ERE for the first line of a multi-line entry
        glob: false                     # read the newest file matching path

**Elasticsearch log rules**: a `frequency` rule alerts on matching documents, a `flatline` rule when a source goes quiet.

    monitoring_es_logs_watch:
      url: http://127.0.0.1:9200
      username: ""
      password: ""
      timeout: 10                       # seconds per query
      rules:
        - name: nginx_errors
          title: Nginx errors
          type: frequency               # or flatline
          index: "nginx-*"
          timeframe_minutes: 5
          query_key: host.name          # one alert per value
          text_template: "Host: {host.name}\n\n{message}"
          timestamp_field: "@timestamp"
          filter: {query_string: {query: "level:error"}}   # frequency
          threshold: 1
          realert_minutes: 15                              # frequency
          # baseline_hours: 24                             # flatline

**MySQL**: the checks connect as root through `/root/.my.cnf`.

    monitoring_mysql_replication_watch:
      max_lag_seconds: 7200
    monitoring_mysql_query_checks:
      - name: time-zones
        query: SELECT COUNT(*) FROM mysql.time_zone_name   # one number
        min: 1                                             # and/or max
    monitoring_slow_query_watch:
      slow_log_path: /var/log/mysql/mysql-slow.log
      min_query_time: 1.0               # seconds
      min_rows_examined: 100000
      min_examined_sent_ratio: 1000     # above this, "possible missing index"
      min_calls: 5
      max_alerts_per_run: 5
      known_retention_days: 30
    monitoring_table_fragmentation_watch:
      min_free_mb: 1024
      min_free_pct: 25

The first `slow-queries` run records existing queries without alerting.

**Applications**

    monitoring_wp_admins_checks:
      - {name: blog, database: wordpress, table_prefix: wp_, multisite: false}
    monitoring_failed_jobs_checks:
      - {name: app, database: app, table: failed_jobs, window_days: 7}
    monitoring_horizon_failed_jobs_checks:
      - {name: app, redis_host: 127.0.0.1, redis_port: 6379, redis_db: 0, prefix: "horizon:"}
    monitoring_sentry_events_watch:
      api_url: http://127.0.0.1:9000/api/0/organizations/ORG/stats_v2/?...
      api_token: ""
      compose_project: sentry-self-hosted

**Backups**

    monitoring_b2_backup_watch:
      bucket: my-backups
      folders: [db]                     # newest file named YYYYMMDDTHHMMSS
      max_age_hours: 26
      env: {B2_APPLICATION_KEY_ID: "", B2_APPLICATION_KEY: ""}
    monitoring_s3_backup_watch:
      region: eu-west-1
      credentials: default
      checks:
        - {bucket: my-backups, prefix: db/, max_age_hours: 26, min_size: 1024, name: db}

**AWS**: `credentials` is `default` (the boto3 credential chain) or `instance-profile` (EC2 metadata only). A tag limits the check to matching resources.

    monitoring_alb_targets_watch:
      {region: eu-west-1, credentials: default, tag_key: "", tag_value: "", consecutive: 2}
    monitoring_cpu_credits_watch:
      {region: eu-west-1, credentials: default, tag_key: "", tag_value: "",
       drop_percent: 25, window_hours: 6, floor: 20}
    monitoring_ses_quota_watch:
      {region: eu-west-1, credentials: default, threshold_percent: 80}

Usage
-----

### Sending messages

Checks, custom ones included, report through `monitoring-notify`:

    monitoring-notify alert KEY MESSAGE         # raise; sent once per KEY
    monitoring-notify clear KEY MESSAGE         # recovery, if KEY was raised
    monitoring-notify resolve PREFIX [KEY...]   # clear every PREFIX* key not listed
    monitoring-notify send MESSAGE ["Label: value"...]   # one-off, with optional fields
    monitoring-notify sms TEXT NUMBER...        # SMS to the given numbers
    monitoring-notify test                      # one message per status

The first line of a message is its title. Active alerts are files in `/var/lib/monitoring/alerts`, so `ls` shows what is failing.

### SMS

An alert whose key matches `monitoring_sms_keys` also sends an SMS when raised and when cleared, never as a reminder. SMS go through the Vonage Messages API with a JWT signed by the application's private key, so the account secret never reaches the host.

### Custom checks

Ship your own script as a template; the dispatcher runs it like the built-in ones.

    monitoring_custom_checks:
      - name: queue-size              # installed as check-queue-size
        src: check-queue-size.sh.j2
        every: 5                      # minutes

A check exits 0 when it ran, whatever it found, and reports through `monitoring-notify`. A non-zero exit means it could not run: the dispatcher alerts with its last line of stderr, so make that line say why.

### Maintenance

    touch /var/lib/monitoring/maintenance   # mute everything
    rm /var/lib/monitoring/maintenance      # unmute

Checks keep running while muted, but nothing is sent or recorded.

### Privacy

Some alerts carry host data to Slack or Telegram: `wp-admins` lists administrator logins and emails, and `logfiles`, `journal` and `es-logs` forward the matching log lines.

Dependencies
------------

None

Testing
-------

    molecule test

License
-------

MIT

Author Information
------------------

[@boutetnico](https://github.com/boutetnico)
