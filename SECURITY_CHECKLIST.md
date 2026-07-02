"""
ENTERPRISE LLM GATEWAY - SECURITY CHECKLIST

Complete this checklist before deploying to production.
"""

========================================================================
PRE-DEPLOYMENT SECURITY CHECKLIST
========================================================================

CREDENTIALS & SECRETS
────────────────────
☐ Client ID obtained from official IT channel (not email)
☐ Client Secret securely stored (not in logs, not in code)
☐ Both credentials encrypted at rest
☐ credentials.env file exists and is git-ignored
☐ credentials.env permissions set to 600 (owner read/write only)
☐ Credentials NOT logged anywhere (verify logs are masked)
☐ No credentials in .env.example or env.template
☐ Credentials rotated within last 90 days
☐ Old credentials revoked after new ones deployed
☐ Backup credentials stored in secure vault (if applicable)

CODE SECURITY
─────────────
☐ No hardcoded API keys in source code
☐ No hardcoded URLs (use environment variables)
☐ No credentials in error messages
☐ No tokens logged to stdout/stderr
☐ Client secrets masked in debug logs
☐ No password/token in git history (check with: git log -p | grep -i secret)
☐ Dependencies updated to latest secure versions
☐ No vulnerable packages in requirements.txt (check with: pip audit)
☐ Code reviewed by security team
☐ Code scanned with static analysis (bandit, semgrep, etc.)

NETWORK SECURITY
────────────────
☐ VERIFY_SSL=true in production environment
☐ SSL certificate validation enabled
☐ TLS 1.2 or higher enforced
☐ Certificate pinning considered (if high security needed)
☐ Firewall rules allow access to OAuth2 and LLM endpoints only
☐ No direct internet access from application server
☐ Requests go through corporate proxy if applicable
☐ Network traffic encrypted in transit (HTTPS only)
☐ Firewall rules whitelist specific IPs if possible
☐ Rate limiting enforced at network level
☐ DDoS protection enabled
☐ IP allowlisting configured with IT

AUTHENTICATION & AUTHORIZATION
───────────────────────────────
☐ OAuth2 client credentials flow properly implemented
☐ Client ID + Secret combination validated
☐ Token scope limited to minimum necessary (e.g., "api" not "admin")
☐ Token expiration set to reasonable value (e.g., 1 hour)
☐ Token refresh logic tested and working
☐ No infinite token lifetime
☐ Token revocation tested and working
☐ Multi-factor authentication enabled for credential management (if applicable)
☐ Service account has minimal permissions needed
☐ Project ID correctly set and validated
☐ No access to other projects/environments

CONFIGURATION & DEPLOYMENT
──────────────────────────
☐ Separate credentials for dev/staging/production
☐ Production credentials never used in development
☐ Environment variables properly set in production
☐ No environment variables exposed in logs
☐ Configuration validation on startup (fails fast)
☐ Configuration changes logged and audited
☐ Deployment process uses secure credential injection
☐ No secrets passed through CLI arguments
☐ No secrets in Docker ENV (use Docker secrets/Kubernetes secrets)
☐ Container scanning for embedded secrets
☐ No .env files committed to git
☐ .env files in .gitignore
☐ Pre-commit hooks prevent accidental commits of secrets

ERROR HANDLING & LOGGING
─────────────────────────
☐ Errors don't expose sensitive information
☐ Error messages don't include tokens or credentials
☐ 401/403 errors logged separately for audit
☐ All authentication failures logged
☐ Failed token requests logged and alerted
☐ Rate limit errors handled gracefully
☐ Network errors don't expose stack traces
☐ Logs stored securely (not in world-readable location)
☐ Log retention policy defined (e.g., 30 days)
☐ Log access restricted to authorized personnel
☐ Log rotation configured
☐ Sensitive fields redacted in logs (test with: grep -i "secret\|password\|token")

MONITORING & ALERTING
─────────────────────
☐ Authentication failures monitored
☐ Token generation failures alerted
☐ Rate limiting events tracked
☐ API error rates monitored
☐ Unusual access patterns detected
☐ Failed credential attempts logged
☐ Token expiration warnings configured
☐ Service availability monitoring enabled
☐ Performance metrics tracked
☐ Security log aggregation set up
☐ Alert thresholds defined
☐ On-call rotation for security alerts

TESTING & VALIDATION
────────────────────
☐ Unit tests for token generation
☐ Tests for failed authentication
☐ Tests for credential validation
☐ Tests for error handling
☐ Integration tests with staging gateway
☐ Load testing with expected traffic
☐ Security tests (invalid creds, timeout, etc.)
☐ Penetration testing completed (if required)
☐ Fallback providers tested
☐ Retry logic tested
☐ Token refresh tested under load
☐ Rate limiting tested

INCIDENT & RECOVERY
───────────────────
☐ Incident response plan created
☐ Rollback procedure documented and tested
☐ Backup/fallback providers functional
☐ Disaster recovery tested
☐ Data backup strategy defined
☐ Crisis communication plan ready
☐ On-call contacts identified
☐ Escalation procedures documented
☐ Service level agreements defined
☐ Metrics for incident response time set

DOCUMENTATION & TRAINING
──────────────────────────
☐ Security requirements documented
☐ Credential management procedures documented
☐ Deployment procedures documented
☐ Incident response procedures documented
☐ Development team trained on security
☐ Operations team trained on security
☐ Security best practices documented
☐ Common vulnerabilities documented
☐ Troubleshooting guide includes security aspects
☐ Security policy provided to team

COMPLIANCE & AUDIT
──────────────────
☐ Data handling policy reviewed
☐ Privacy requirements met
☐ Regulatory compliance verified (HIPAA, SOC2, etc.)
☐ Audit logging configured
☐ Compliance scan passed
☐ Compliance documentation updated
☐ Third-party audit scheduled (if required)
☐ Compliance violations logged and tracked
☐ Access logs maintained for audit
☐ Change management process followed

OPERATIONAL SECURITY
────────────────────
☐ Credentials stored in secure vault (not .env file)
☐ Vault access controlled and audited
☐ Credential rotation scheduled
☐ No credentials in version control
☐ Access control list maintained
☐ Least privilege principle applied
☐ No shared credentials (unique per service)
☐ Service account has no human user access
☐ No sudo/admin access needed for normal operation
☐ Backup credentials tested quarterly
☐ Certificate expiration monitored

THIRD-PARTY & DEPENDENCIES
───────────────────────────
☐ All dependencies vetted for security
☐ No unnecessary dependencies included
☐ Dependency versions pinned
☐ Vulnerable version alerts configured
☐ Automated dependency updates planned
☐ Security advisories monitored
☐ Third-party service security reviewed
☐ SLA and security guarantees obtained
☐ Third-party access properly scoped
☐ Third-party changes reviewed

========================================================================
ADDITIONAL SECURITY MEASURES (RECOMMENDED)
========================================================================

ADVANCED MEASURES
─────────────────
☐ Implement rate limiting on token endpoint
☐ Implement CORS restrictions
☐ Use API gateway with security policies
☐ Implement request signing (if supported)
☐ Use mutual TLS (mTLS) authentication
☐ Implement request encryption
☐ Use service mesh for network security
☐ Implement secrets rotation automation
☐ Use hardware security module (HSM) for keys
☐ Implement zero-trust architecture principles
☐ Regular security vulnerability assessments
☐ Red team testing
☐ Blue team exercises

MONITORING ENHANCEMENTS
───────────────────────
☐ Implement SIEM (Security Information & Event Management)
☐ Set up anomaly detection for authentication
☐ Monitor for credential stuffing attempts
☐ Track unusual token usage patterns
☐ Monitor for rate limit abuse
☐ Track API error rates
☐ Monitor network traffic anomalies
☐ Set up honey tokens (fake credentials) to detect compromises
☐ Implement continuous security monitoring
☐ Set up automated incident detection

DATA PROTECTION
───────────────
☐ Data in transit encrypted (TLS 1.2+)
☐ Data at rest encrypted (if stored)
☐ Database connections encrypted
☐ Secrets not stored in application memory (if possible)
☐ Memory cleared after use
☐ No secrets in debug output
☐ Prompt/response data handled securely
☐ User data privacy respected
☐ GDPR compliance (if applicable)
☐ Data retention policy implemented
☐ Secure data deletion procedure

========================================================================
SECURITY AUDIT QUESTIONS
========================================================================

Questions to answer before production:

1. How are credentials protected?
   → credentials.env file, file permissions 600, encrypted at rest

2. What if credentials are compromised?
   → Immediate rotation, old credentials revoked, incident response

3. How are tokens secured?
   → Cached in memory, cleared on shutdown, not logged

4. What if the OAuth2 server is down?
   → Falls back to Azure or Groq provider

5. How is communication encrypted?
   → HTTPS/TLS only, certificate validation enabled

6. Who has access to credentials?
   → Only application servers and authorized ops staff

7. How are credentials rotated?
   → Scheduled quarterly, tested before deployment

8. What if application is compromised?
   → Credentials isolated, revocation procedure, audit logs

9. How are logs secured?
   → Encrypted storage, restricted access, audit trail

10. What happens on security incident?
    → Incident response plan, communication protocol, recovery procedure

========================================================================
REMEDIATION ACTIONS
========================================================================

If any checkbox is unchecked, create a remediation task:

Format:
  [ ] Unchecked item
      Priority: High/Medium/Low
      Owner: [Name]
      Timeline: [Date]
      Details: [What needs to be done]

Example:
  [ ] Service account has admin access
      Priority: High
      Owner: DevOps Team
      Timeline: 2026-06-15
      Details: Create new service account with minimal permissions

========================================================================
SIGN-OFF
========================================================================

After completing all applicable items:

I, _________________________ (Name & Title)
have reviewed this security checklist and confirm that the Enterprise
LLM Gateway integration meets our organization's security standards
and is ready for production deployment.

Date: __________________

Security Review: _________________________ (Security Officer)
DevOps Review: _________________________ (DevOps Lead)
Development Review: _________________________ (Tech Lead)

========================================================================
PERIODIC REVIEW
========================================================================

This checklist should be reviewed:
- ☐ Before each production deployment
- ☐ Quarterly (every 3 months)
- ☐ After any security incident
- ☐ After major code changes
- ☐ After credential rotation
- ☐ After security advisories

Review dates:
- [ ] 2026-06-06 - Initial deployment
- [ ] 2026-09-06 - Q3 review
- [ ] 2026-12-06 - Q4 review
- [ ] 2027-03-06 - Q1 review

========================================================================
"""
