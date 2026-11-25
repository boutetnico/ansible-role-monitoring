import json
import pytest

BIN = "/usr/local/bin"
ALERTS = "/var/lib/monitoring/alerts"

SHELL_CHECKS = [
    "systemd-failures",
    "services",
    "journal",
    "ip-pool",
    "logfiles",
    "disk-usage",
    "wp-admins",
    "failed-jobs",
    "sentry-events",
    "b2-backups",
    "posture",
    "apt-security",
    "reboot-required",
    "files",
    "table-fragmentation",
    "mysql-replication",
    "mysql-queries",
    "custom",
]

PYTHON_CHECKS = [
    "es-logs",
    "horizon-failed-jobs",
    "alb-targets",
    "slow-queries",
    "cpu-credits",
    "s3-backups",
    "ses-quota",
]


@pytest.mark.parametrize("name", SHELL_CHECKS + PYTHON_CHECKS)
def test_check_installed(host, name):
    f = host.file(f"{BIN}/check-{name}")
    assert f.exists
    assert f.user == "root"
    assert f.mode == 0o700


@pytest.mark.parametrize("name", SHELL_CHECKS)
def test_shell_check_is_valid(host, name):
    assert host.run(f"bash -n {BIN}/check-{name}").rc == 0
    result = host.run(f"shellcheck -S warning {BIN}/check-{name}")
    assert result.rc == 0, result.stdout


@pytest.mark.parametrize("name", PYTHON_CHECKS + ["monitoring-notify"])
def test_python_script_compiles(host, name):
    path = f"{BIN}/{name}" if name == "monitoring-notify" else f"{BIN}/check-{name}"
    result = host.run(f"python3 -m py_compile {path}")
    assert result.rc == 0, result.stderr


def test_secrets_are_not_passed_as_arguments(host):
    services = host.file(f"{BIN}/check-services").content_string
    assert "probe-secret" not in services
    assert "X-Probe-Token: token-secret" in services
    assert "-H 'X-Probe-Token" not in services
    assert "-u " not in services
    assert "-H @-" in services
    sentry = host.file(f"{BIN}/check-sentry-events").content_string
    assert "Bearer %s" in sentry
    assert "-H @-" in sentry


def test_notifier_pages_only_matching_keys(host):
    notify = host.file(f"{BIN}/monitoring-notify").content_string
    assert "test-application" in notify
    assert "api.nexmo.com/v1/messages" in notify
    assert not host.file("/var/lib/monitoring/vonage.key").exists
    assert host.run(f"{BIN}/monitoring-notify alert other-key down").rc == 0
    assert host.file(f"{ALERTS}/other-key").exists
    assert host.run(f"{BIN}/monitoring-notify clear other-key up").rc == 0


def test_dispatcher_runs_checks_on_their_interval(host):
    script = host.file(f"{BIN}/monitoring-dispatch")
    assert script.contains("run logfiles 5")
    assert script.contains("run disk-usage 10")
    assert script.contains("run custom 15")
    assert script.contains("run files 1440")
    assert host.run(f"bash -n {BIN}/monitoring-dispatch").rc == 0


def test_timer_unit(host):
    timer = host.file("/etc/systemd/system/monitoring-checks.timer").content_string
    assert "OnCalendar=*-*-* *:*:00" in timer
    service = host.file("/etc/systemd/system/monitoring-checks.service").content_string
    assert f"ExecStart={BIN}/monitoring-dispatch" in service


def notify(host, *args):
    quoted = " ".join(f"'{a}'" for a in args)
    return host.run(f"{BIN}/monitoring-notify {quoted}")


def test_notifier_alert_clear_and_resolve(host):
    host.run(f"rm -rf {ALERTS}/test-*")
    assert notify(host, "alert", "test-a", "a is down").rc == 0
    assert notify(host, "alert", "test-b", "b is down").rc == 0
    assert host.file(f"{ALERTS}/test-a").content_string == "a is down"

    assert notify(host, "clear", "test-a", "a is back").rc == 0
    assert not host.file(f"{ALERTS}/test-a").exists

    assert notify(host, "alert", "test-c", "c is down").rc == 0
    assert notify(host, "resolve", "test-", "test-c").rc == 0
    assert not host.file(f"{ALERTS}/test-b").exists
    assert host.file(f"{ALERTS}/test-c").exists
    assert notify(host, "resolve", "test-").rc == 0
    assert not host.file(f"{ALERTS}/test-c").exists


def test_notifier_is_muted_during_maintenance(host):
    host.run(f"rm -rf {ALERTS}/test-*")
    host.run("touch /var/lib/monitoring/maintenance")
    assert notify(host, "alert", "test-muted", "muted").rc == 0
    host.run("rm -f /var/lib/monitoring/maintenance")
    assert not host.file(f"{ALERTS}/test-muted").exists


def test_logfile_check_reads_only_new_lines(host):
    log = "/var/log/test-app.log"
    key = f"{ALERTS}/logfiles-app"
    host.run(f"rm -f {key} /var/lib/monitoring/check-logfiles/app.offset")
    host.run(f"echo 'ERROR: old entry' > {log}")
    host.run(f"{BIN}/check-logfiles")
    assert not host.file(key).exists

    host.run(f"echo 'error, lower case' >> {log}")
    host.run(f"echo 'ERROR: expected noise' >> {log}")
    host.run(f"{BIN}/check-logfiles")
    assert not host.file(key).exists

    host.run(f"echo 'ERROR: something broke' >> {log}")
    host.run(f"{BIN}/check-logfiles")
    assert host.file(key).exists
    assert "something broke" in host.file(key).content_string

    host.run(f"{BIN}/check-logfiles")
    assert not host.file(key).exists


def test_logfile_check_joins_entries_and_needs_min_matches(host):
    log = "/var/log/test-nginx-error.log"
    key = f"{ALERTS}/logfiles-nginx"
    host.run(f"rm -f {key} /var/lib/monitoring/check-logfiles/nginx.offset")
    host.run(f"touch {log}")
    host.run(f"{BIN}/check-logfiles")

    host.run(f"echo '2025/01/01 00:00:00 [error] first' >> {log}")
    host.run(f"echo '  continued line' >> {log}")
    host.run(f"{BIN}/check-logfiles")
    assert not host.file(key).exists

    host.run(f"echo '2025/01/01 00:00:01 [error] one' >> {log}")
    host.run(f"echo '2025/01/01 00:00:02 [crit] two' >> {log}")
    host.run(f"{BIN}/check-logfiles")
    assert host.file(key).exists


def test_file_check(host):
    host.run(f"rm -f {ALERTS}/files-*")
    assert host.run(f"{BIN}/check-files").rc == 0
    assert host.file(f"{ALERTS}/files-_var_lib_app_data.mmdb").exists
    assert not host.file(f"{ALERTS}/files-_etc_hostname").exists


def test_reboot_required_check(host):
    key = f"{ALERTS}/reboot-required"
    host.run("touch /var/run/reboot-required")
    assert host.run(f"{BIN}/check-reboot-required").rc == 0
    assert host.file(key).exists
    host.run("rm -f /var/run/reboot-required")
    assert host.run(f"{BIN}/check-reboot-required").rc == 0
    assert not host.file(key).exists


def test_mysql_replication_check(host):
    threads = f"{ALERTS}/mysql-replication-threads"
    lag = f"{ALERTS}/mysql-replication-lag"

    def replica(io, behind):
        host.run(
            "printf '%s\\n' '#!/bin/sh' "
            f"'printf \"Replica_IO_Running: {io}\\nReplica_SQL_Running: Yes\\n"
            f"Seconds_Behind_Source: {behind}\\nLast_IO_Error: boom\\n\"' "
            "> /usr/bin/mysql && chmod +x /usr/bin/mysql"
        )
        assert host.run(f"{BIN}/check-mysql-replication").rc == 0

    replica("No", "NULL")
    assert host.file(threads).exists
    assert "boom" in host.file(threads).content_string
    replica("Yes", 5000)
    assert not host.file(threads).exists
    assert host.file(lag).exists
    replica("Yes", 10)
    assert not host.file(lag).exists
    host.run("rm -f /usr/bin/mysql")


def test_notifier_signs_a_valid_vonage_token(host):
    key = "/var/lib/monitoring/vonage.key"
    host.run(
        f"openssl genpkey -algorithm RSA -out {key} && openssl pkey -in {key} -pubout -out /tmp/vonage.pub"
    )
    result = host.run(
        "python3 -c 'import runpy; "
        f'n = runpy.run_path("{BIN}/monitoring-notify", run_name="n"); '
        'print(n["vonage_token"]())\''
    )
    host.run(f"rm -f {key}")
    assert result.rc == 0, result.stderr
    header, claims, signature = result.stdout.strip().split(".")
    check = host.run(
        "python3 - <<'EOF'\n"
        "import base64, json, subprocess\n"
        f"h, c, s = {header!r}, {claims!r}, {signature!r}\n"
        "pad = lambda x: x + '=' * (-len(x) % 4)\n"
        "assert json.loads(base64.urlsafe_b64decode(pad(c)))['application_id'] == 'test-application'\n"
        "open('/tmp/sig', 'wb').write(base64.urlsafe_b64decode(pad(s)))\n"
        "subprocess.run(['openssl', 'dgst', '-sha256', '-verify', '/tmp/vonage.pub', '-signature', '/tmp/sig'],"
        " input=f'{h}.{c}'.encode(), check=True)\n"
        "EOF"
    )
    assert check.rc == 0, check.stdout + check.stderr


def test_es_logs_reports_a_timeout(host):
    host.run(
        "nohup python3 -c 'import socket, time; s = socket.socket(); "
        's.bind(("127.0.0.1", 9200)); s.listen(); time.sleep(10)\' >/dev/null 2>&1 &'
    )
    host.run("sleep 1")
    result = host.run(f"{BIN}/check-es-logs")
    assert result.rc == 1
    assert "(Elasticsearch did not answer within 1s)" in result.stderr


def test_sentry_events_reports_why_the_api_failed(host):
    result = host.run(f"{BIN}/check-sentry-events")
    assert result.rc == 1
    assert any(
        reason in result.stderr
        for reason in ("Sentry API unreachable: curl:", "Sentry API returned HTTP")
    )


def test_notifier_formats_slack_attachments(host):
    result = host.run(
        "python3 -c 'import json, runpy; "
        f'n = runpy.run_path("{BIN}/monitoring-notify", run_name="n"); '
        'print(json.dumps([n["slack_payload"]("db <down>\\nrows: 3", "alert"), '
        'n["slack_payload"]("db up", "recovered", ["Max time: 1:02 <s>"])]))\''
    )
    assert result.rc == 0, result.stderr
    alert, recovered = (p["attachments"][0] for p in json.loads(result.stdout))
    assert alert["text"] == "*db &lt;down&gt;*\nrows: 3"
    assert alert["color"] != recovered["color"]
    assert alert["footer"].endswith(" · alert")
    assert recovered["text"] == "*db up*"
    assert alert["fields"] == []
    assert recovered["fields"] == [
        {"short": True, "title": "Max time", "value": "1:02 &lt;s&gt;"}
    ]


def test_mysql_query_check(host):
    key = f"{ALERTS}/mysql-queries-time-zones"

    def returns(output, rc=0):
        host.run(
            f"printf '%s\\n' '#!/bin/sh' 'echo \"{output}\"' 'exit {rc}' "
            "> /usr/bin/mysql && chmod +x /usr/bin/mysql"
        )
        assert host.run(f"{BIN}/check-mysql-queries").rc == 0

    returns(0)
    assert "below 1" in host.file(key).content_string
    returns(500)
    assert not host.file(key).exists
    assert "above 100" in host.file(f"{ALERTS}/mysql-queries-queue").content_string
    returns("Access denied", 1)
    assert "failed: Access denied" in host.file(key).content_string
    returns(5)
    assert not host.file(key).exists
    host.run("rm -f /usr/bin/mysql")
