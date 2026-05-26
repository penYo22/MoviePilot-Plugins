/**
 * Federation Exposed Module: ./Page
 *
 * NOTE: This file is hand-crafted. Regenerate via `npm run build` in the
 * frontend/ directory when source changes, then copy dist/assets/ output here.
 */
import { h, resolveComponent } from 'vue';

const Page = {
  name: 'Page',
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
            h(VIcon, { class: 'mr-2' }, () => 'mdi-view-dashboard'),
            '\u81EA\u5B9A\u4E49\u7F8E\u5316\u9875\u9762'
          ]),
          h(VCardText, null, () => [
            h(VAlert, { type: 'info', variant: 'tonal' }, () =>
              '\u6B64\u63D2\u4EF6\u901A\u8FC7\u4FA7\u680F\u300C\u7F8E\u5316\u9996\u9875\u300D\u5165\u53E3\u5C55\u793A\u81EA\u5B9A\u4E49\u4EEA\u8868\u677F\u9875\u9762\u3002\u8BF7\u901A\u8FC7\u4FA7\u680F\u5BFC\u822A\u8BBF\u95EE\u5B8C\u6574\u7684\u4EEA\u8868\u677F\u89C6\u56FE\u3002'
            )
          ])
        ])
      ]);
    };
  }
};

export default Page;
