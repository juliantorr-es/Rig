export const RigLog = {
  debug(area, message, data) {
    if (window.console && console.debug) console.debug(`[${area}] ${message}`, data || {});
  },
  info(area, message, data) {
    if (window.console && console.info) console.info(`[${area}] ${message}`, data || {});
  },
  warn(area, message, data) {
    if (window.console && console.warn) console.warn(`[${area}] ${message}`, data || {});
  },
  _redactSecrets(value) {
    return String(value || '');
  },
};

window.RigLog = window.RigLog || RigLog;
