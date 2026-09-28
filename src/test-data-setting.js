export function isTestDataEnabled(storage) {
  return storage?.getItem('cirava.testMode') === 'true';
}
