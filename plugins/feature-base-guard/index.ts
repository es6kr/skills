import { definePluginEntry } from 'openclaw/plugin-sdk/plugin-entry';
import { register } from './policy.mjs';
export default definePluginEntry({
  id: 'feature-base-guard',
  name: 'Feature base guard',
  description: 'Pinned feature-base verification and a terminal veto for supported structured Git actions.',
  register,
});
