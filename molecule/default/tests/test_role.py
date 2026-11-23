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
    assert "-u " not in services
    assert "-H @-" in services
    sentry = host.file(f"{BIN}/check-sentry-events").content_string
    assert "Bearer %s" in sentry
    assert "-H @-" in sentry


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
