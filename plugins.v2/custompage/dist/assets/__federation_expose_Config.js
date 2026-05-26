/**
 * Federation Exposed Module: ./Config
 *
 * NOTE: This file is hand-crafted. Regenerate via `npm run build` in the
 * frontend/ directory when source changes, then copy dist/assets/ output here.
 */
import { h, resolveComponent } from 'vue';

const Config = {
  name: 'Config',
  props: {
    api: { type: Object, default: () => ({}) },
    pluginId: { type: String, default: '' }
  },
  setup(props) {
    return () => {
      const VContainer = resolveComponent('v-container');
      const VCard = resolveComponent('v-card');
      const VCardTitle = resolveComponent('v-card-title');
      const VCardText = resolveComponent('v-card-text');
      const VIcon = resolveComponent('v-icon');
      const VAlert = resolveComponent('v-alert');

      return h(VContainer, { fluid: true, class: 'pa-4' }, () => [
        h(VCard, { class: 'rounded-lg', variant: 'outlined' }, () => [
          h(VCardTitle, { class: 'text-h6' }, () => [
            h(VIcon, { class: 'mr-2' }, () => 'mdi-cog'),
            '\u63D2\u4EF6\u914D\u7F6E'
          ]),
          h(VCardText, null, () => [
            h(VAlert, { type: 'info', variant: 'tonal', class: 'mb-4' }, () =>
              '\u81EA\u5B9A\u4E49\u7F8E\u5316\u9875\u9762\u63D2\u4EF6\u914D\u7F6E\u3002\u542F\u7528\u540E\u5C06\u5728\u4FA7\u680F\u6DFB\u52A0\u300C\u7F8E\u5316\u9996\u9875\u300D\u5BFC\u822A\u5165\u53E3\u3002'
            )
          ])
        ])
      ]);
    };
  }
};

export default Config;
