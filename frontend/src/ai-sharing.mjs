// Permission is for a recipient, not a blanket permission for any future provider.
export function canShare(status, permissionId) {
  return !!(status?.ready && typeof status.consent_id==='string' &&
    status.consent_id.length===64 && permissionId===status.consent_id);
}

export function recipient(status) {
  return status?.provider_label || 'the selected AI provider';
}
