// frontend/src/debugger.js
export function initDebugger(app) {
  const LOG_KEY = 'eduai_debug_logs';
  
  function saveLog(type, message, details = '') {
    try {
      const logs = JSON.parse(localStorage.getItem(LOG_KEY) || '[]');
      logs.push({
        time: new Date().toISOString(),
        type,
        message: String(message),
        details: String(details)
      });
      // Keep only last 100 to avoid performance issues
      if (logs.length > 100) logs.shift();
      localStorage.setItem(LOG_KEY, JSON.stringify(logs));
    } catch (e) {
      // ignore
    }
  }

  // Clear on fresh load? No, we want to keep them across crashes.
  // We'll just append.

  // Global window error
  window.addEventListener('error', (event) => {
    saveLog('WINDOW_ERROR', event.message, `${event.filename}:${event.lineno}:${event.colno}`);
  });

  // Unhandled promise rejection
  window.addEventListener('unhandledrejection', (event) => {
    saveLog('PROMISE_ERROR', event.reason?.message || String(event.reason), event.reason?.stack || '');
  });

  // Vue error handler
  if (app) {
    app.config.errorHandler = (err, instance, info) => {
      saveLog('VUE_ERROR', err.message, `${info}\n${err.stack}`);
      console.error('Vue Error caught by debugger:', err, info);
    };
  }

  // Hook into console.error and console.warn
  const origError = console.error;
  const origWarn = console.warn;

  console.error = (...args) => {
    saveLog('CONSOLE_ERROR', args.join(' '));
    origError.apply(console, args);
  };
  
  console.warn = (...args) => {
    saveLog('CONSOLE_WARN', args.join(' '));
    origWarn.apply(console, args);
  };
  
  // Expose a way for the user to download logs
  window.downloadCrashLogs = () => {
    const logs = localStorage.getItem(LOG_KEY) || '[]';
    const blob = new Blob([logs], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `eduai-crash-logs-${new Date().toISOString().replace(/:/g, '-')}.json`;
    a.click();
    console.log("Логи успешно скачаны!");
  };
  
  // Clear logs manually
  window.clearCrashLogs = () => {
    localStorage.removeItem(LOG_KEY);
    console.log("Логи очищены!");
  };

  console.log("%c Дебаггер активен. Если браузер вылетает, после перезапуска введите в консоли: downloadCrashLogs()", "background: #222; color: #bada55; padding: 5px;");
}
