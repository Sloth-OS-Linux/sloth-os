/*
 * pam_sloth_pin: signing in with the PIN (Sloth Center -> Account and security -> PIN).
 *
 * It takes the place of the earlier pam_exec + pin-check line, so it can do one thing pam_exec cannot: hand the
 * account's real password on to the modules after it. With a TPM, setting the PIN together with the password keeps
 * the password encrypted with a key that only the right PIN gets out of the TPM (pin-verifier). On the sign-in
 * screen (run by root) the right PIN brings the password back, and this module puts it in PAM_AUTHTOK, so
 * pam_kwallet opens the password store (KWallet) the same as after typing the password. Like Windows Hello.
 *
 * The typed text: anything that is not 4-8 digits is a password and goes on to pam_unix untouched (PAM_IGNORE).
 * The PIN is only accepted locally, in the allowed services; never for a remote login. The check itself is done by
 * the PIN's keeper (/usr/libexec/sloth-os/pin-verifier, root, behind /run/sloth-os/pin.sock); it gives the password
 * back only to root and only for a sign-in service, never to the lock screen (it runs in the user's name and the
 * store is open by then anyway).
 *
 * Any error is a "no": an error must never let anyone in, nor stop the password from working.
 * Built during the image build by files/scripts/pam-sloth-pin.sh (the build tools are removed again).
 */
#define PAM_SM_AUTH
#include <ctype.h>
#include <errno.h>
#include <poll.h>
#include <security/pam_ext.h>
#include <security/pam_modules.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <syslog.h>
#include <unistd.h>

#define SOCKET_PATH "/run/sloth-os/pin.sock"
#define MAX_PASSWORD 512

static const char *const SERVICES[] = {"login", "sddm", "plasmalogin", "plasma-login", "kde", "kscreensaver",
                                       "kscreenlocker", "polkit-1", "sudo", "sudo-i", "su", "su-l", NULL};

static int allowed_service(const char *service)
{
    for (int i = 0; SERVICES[i]; i++)
        if (strcmp(service, SERVICES[i]) == 0)
            return 1;
    return 0;
}

/* The same account names pin-verifier accepts: [a-z_][a-z0-9_.-]{0,31} (so nothing needs quoting in the JSON) */
static int valid_user(const char *user)
{
    size_t n = strlen(user);
    if (n == 0 || n > 32 || !(islower((unsigned char)user[0]) || user[0] == '_'))
        return 0;
    for (size_t i = 1; i < n; i++) {
        unsigned char c = (unsigned char)user[i];
        if (!(islower(c) || isdigit(c) || c == '_' || c == '.' || c == '-'))
            return 0;
    }
    return 1;
}

static int is_pin(const char *tok)
{
    size_t n = strlen(tok);
    if (n < 4 || n > 8)
        return 0;
    for (size_t i = 0; i < n; i++)
        if (!isdigit((unsigned char)tok[i]))
            return 0;
    return 1;
}

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

/* Sends the request, reads the answer ("ok", "ok <the password in hex>" or "no") into buf. */
static int ask(const char *request, char *buf, size_t size)
{
    int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (fd < 0)
        return -1;
    struct sockaddr_un addr = {.sun_family = AF_UNIX};
    strncpy(addr.sun_path, SOCKET_PATH, sizeof(addr.sun_path) - 1);
    size_t len = strlen(request), done = 0, got = 0;
    int ok = -1;
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0)
        goto out;
    while (done < len) {
        ssize_t w = write(fd, request + done, len - done);
        if (w <= 0)
            goto out;
        done += (size_t)w;
    }
    while (got < size - 1) {
        struct pollfd p = {.fd = fd, .events = POLLIN};
        if (poll(&p, 1, 30000) <= 0)       /* a TPM can take a second or two */
            goto out;
        ssize_t r = read(fd, buf + got, size - 1 - got);
        if (r < 0 && errno == EINTR)
            continue;
        if (r <= 0)
            break;
        got += (size_t)r;
        if (memchr(buf, '\n', got))
            break;
    }
    buf[got] = '\0';
    ok = 0;
out:
    close(fd);
    return ok;
}

PAM_EXTERN int pam_sm_authenticate(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    (void)flags; (void)argc; (void)argv;
    const char *user = NULL, *service = NULL, *rhost = NULL, *tok = NULL;
    if (pam_get_user(pamh, &user, NULL) != PAM_SUCCESS || !user || !valid_user(user))
        return PAM_IGNORE;
    if (pam_get_item(pamh, PAM_SERVICE, (const void **)&service) != PAM_SUCCESS || !service
        || !allowed_service(service))
        return PAM_IGNORE;
    if (pam_get_item(pamh, PAM_RHOST, (const void **)&rhost) == PAM_SUCCESS && rhost && *rhost
        && strcmp(rhost, "localhost") != 0 && strcmp(rhost, "127.0.0.1") != 0 && strcmp(rhost, "::1") != 0)
        return PAM_IGNORE;
    /* asks "Password:" if nothing was typed yet; pam_unix then takes the same text (try_first_pass) */
    if (pam_get_authtok(pamh, PAM_AUTHTOK, &tok, NULL) != PAM_SUCCESS || !tok)
        return PAM_AUTHINFO_UNAVAIL;
    if (!is_pin(tok))
        return PAM_IGNORE;                 /* a password: pam_unix checks it */

    char request[256];
    /* the password back only where the store opens next: the sign-in screen, run by root */
    int want = getuid() == 0 && geteuid() == 0
               && (strcmp(service, "plasmalogin") == 0 || strcmp(service, "plasma-login") == 0
                   || strcmp(service, "sddm") == 0 || strcmp(service, "login") == 0);
    snprintf(request, sizeof(request), "{\"user\": \"%s\", \"pin\": \"%s\", \"service\": \"%s\"%s}\n", user, tok,
             service, want ? ", \"authtok\": true" : "");
    char answer[2 * MAX_PASSWORD + 16];
    int rc = PAM_AUTH_ERR;
    if (ask(request, answer, sizeof(answer)) != 0 || strncmp(answer, "ok", 2) != 0)
        goto done;
    rc = PAM_SUCCESS;
    if (want && answer[2] == ' ') {
        char password[MAX_PASSWORD + 1];
        size_t n = 0;
        const char *p = answer + 3;
        while (n < MAX_PASSWORD && hexval(p[0]) >= 0 && hexval(p[1]) >= 0) {
            password[n++] = (char)(hexval(p[0]) << 4 | hexval(p[1]));
            p += 2;
        }
        password[n] = '\0';
        if (n > 0 && strlen(password) == n && pam_set_item(pamh, PAM_AUTHTOK, password) != PAM_SUCCESS)
            pam_syslog(pamh, LOG_WARNING, "could not hand the password on to the password store");
        explicit_bzero(password, sizeof(password));
    }
done:
    explicit_bzero(answer, sizeof(answer));
    explicit_bzero(request, sizeof(request));
    return rc;
}

PAM_EXTERN int pam_sm_setcred(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    (void)pamh; (void)flags; (void)argc; (void)argv;
    return PAM_SUCCESS;
}
