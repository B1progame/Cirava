/** Hand a checksum-verified staged update to the OS, then close Cirava. */
export async function restartCiravaForUpdate(bridge, staged, updateType) {
  if (!bridge?.restart_staged_update || !bridge?.request_quit) {
    throw new Error('This Cirava build cannot restart itself to apply updates.');
  }
  await bridge.restart_staged_update(staged.path, updateType);
  await bridge.request_quit();
  return { restarted: true, update_type: updateType };
}
