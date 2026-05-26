/**
 * Federation Exposed Module: ./AppPage
 * Beautiful dashboard page with Vuetify components
 */
import { ref, computed, onMounted, onUnmounted, h, resolveComponent } from 'vue';

const AppPage = {
  name: 'AppPage',
  props: {
    api: { type: Object, default: () => ({}) },
    navKey: { type: String, default: '' },
    pluginId: { type: String, default: '' }
  },
  setup(props) {
    const currentTime = ref('');
    const currentDate = ref('');
    let timer = null;

    const greeting = computed(() => {
      const hour = new Date().getHours();
      if (hour < 6) return '\u591C\u6DF1\u4E86\uFF0C\u6CE8\u610F\u4F11\u606F';
      if (hour < 9) return '\u65E9\u4E0A\u597D\uFF0C\u7F8E\u597D\u7684\u4E00\u5929\u5F00\u59CB\u4E86';
      if (hour < 12) return '\u4E0A\u5348\u597D\uFF0C\u5DE5\u4F5C\u987A\u5229';
      if (hour < 14) return '\u4E2D\u5348\u597D\uFF0C\u8BB0\u5F97\u4F11\u606F';
      if (hour < 18) return '\u4E0B\u5348\u597D\uFF0C\u7EE7\u7EED\u52A0\u6CB9';
      if (hour < 22) return '\u665A\u4E0A\u597D\uFF0C\u4EAB\u53D7\u5F71\u97F3\u65F6\u5149';
      return '\u591C\u6DF1\u4E86\uFF0C\u6CE8\u610F\u4F11\u606F';
    });

    const navItems = [
      { title: '\u63A2\u7D22\u53D1\u73B0', desc: '\u53D1\u73B0\u65B0\u5F71\u7247', icon: 'mdi-compass-outline', color: 'blue' },
      { title: '\u6211\u7684\u8BA2\u9605', desc: '\u7BA1\u7406\u8BA2\u9605', icon: 'mdi-heart-outline', color: 'red' },
      { title: '\u4E0B\u8F7D\u7BA1\u7406', desc: '\u67E5\u770B\u4E0B\u8F7D', icon: 'mdi-download', color: 'green' },
      { title: '\u5A92\u4F53\u6574\u7406', desc: '\u6574\u7406\u6587\u4EF6', icon: 'mdi-folder-multiple', color: 'orange' },
      { title: '\u5386\u53F2\u8BB0\u5F55', desc: '\u6D4F\u89C8\u5386\u53F2', icon: 'mdi-history', color: 'purple' },
      { title: '\u7CFB\u7EDF\u8BBE\u7F6E', desc: '\u914D\u7F6E\u7CFB\u7EDF', icon: 'mdi-cog-outline', color: 'grey' }
    ];

    function updateTime() {
      const now = new Date();
      currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false });
      currentDate.value = now.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        weekday: 'long'
      });
    }

    onMounted(() => {
      updateTime();
      timer = setInterval(updateTime, 1000);
    });

    onUnmounted(() => {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    });

    return () => {
      const VContainer = resolveComponent('v-container');
      const VCard = resolveComponent('v-card');
      const VCardText = resolveComponent('v-card-text');
      const VRow = resolveComponent('v-row');
      const VCol = resolveComponent('v-col');
      const VIcon = resolveComponent('v-icon');
      const VList = resolveComponent('v-list');
      const VListItem = resolveComponent('v-list-item');
      const VListItemTitle = resolveComponent('v-list-item-title');
      const VListItemSubtitle = resolveComponent('v-list-item-subtitle');

      // Welcome Banner
      const welcomeBanner = h(VCard, {
        class: 'mb-6 rounded-xl elevation-4',
        style: {
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white'
        }
      }, () => [
        h(VCardText, { class: 'pa-8' }, () => [
          h(VRow, { align: 'center' }, () => [
            h(VCol, { cols: 12, md: 8 }, () => [
              h('h1', { class: 'text-h4 font-weight-bold mb-2' }, greeting.value),
              h('p', {
                class: 'text-subtitle-1 mb-0',
                style: { opacity: '0.9' }
              }, '\u6B22\u8FCE\u4F7F\u7528 MoviePilot\uFF0C\u60A8\u7684\u667A\u80FD\u5F71\u97F3\u7BA1\u7406\u52A9\u624B')
            ]),
            h(VCol, { cols: 12, md: 4, class: 'text-right' }, () => [
              h('div', { class: 'text-h5 font-weight-medium' }, currentTime.value),
              h('div', {
                class: 'text-subtitle-2',
                style: { opacity: '0.8' }
              }, currentDate.value)
            ])
          ])
        ])
      ]);

      // Quick Navigation
      const navHeader = h('h2', { class: 'text-h6 font-weight-bold mb-4' }, [
        h(VIcon, { class: 'mr-2' }, () => 'mdi-compass'),
        '\u5FEB\u6377\u5BFC\u822A'
      ]);

      const navCards = h(VRow, { class: 'mb-6' }, () =>
        navItems.map(nav =>
          h(VCol, { cols: 6, sm: 4, md: 2, key: nav.title }, () => [
            h(VCard, {
              class: 'text-center pa-4 rounded-lg',
              variant: 'outlined',
              hover: true,
              style: { transition: 'transform 0.2s ease, box-shadow 0.2s ease' }
            }, () => [
              h(VIcon, { color: nav.color, size: 40, class: 'mb-2' }, () => nav.icon),
              h('div', { class: 'text-body-2 font-weight-medium' }, nav.title),
              h('div', { class: 'text-caption text-medium-emphasis' }, nav.desc)
            ])
          ])
        )
      );

      // System Info Header
      const sysHeader = h('h2', { class: 'text-h6 font-weight-bold mb-4' }, [
        h(VIcon, { class: 'mr-2' }, () => 'mdi-information-outline'),
        '\u7CFB\u7EDF\u4FE1\u606F'
      ]);

      // System Info Cards
      const sysInfoRow = h(VRow, null, () => [
        h(VCol, { cols: 12, md: 6 }, () => [
          h(VCard, { class: 'rounded-lg', variant: 'outlined' }, () => [
            h(VCardText, null, () => [
              h(VList, { density: 'compact' }, () => [
                h(VListItem, { prependIcon: 'mdi-clock-outline' }, () => [
                  h(VListItemTitle, null, () => '\u5F53\u524D\u65F6\u95F4'),
                  h(VListItemSubtitle, null, () => `${currentTime.value} ${currentDate.value}`)
                ]),
                h(VListItem, { prependIcon: 'mdi-check-circle' }, () => [
                  h(VListItemTitle, null, () => '\u8FD0\u884C\u72B6\u6001'),
                  h(VListItemSubtitle, null, () => '\u7CFB\u7EDF\u8FD0\u884C\u6B63\u5E38')
                ]),
                h(VListItem, { prependIcon: 'mdi-puzzle' }, () => [
                  h(VListItemTitle, null, () => '\u63D2\u4EF6\u7248\u672C'),
                  h(VListItemSubtitle, null, () => 'v1.0')
                ])
              ])
            ])
          ])
        ]),
        h(VCol, { cols: 12, md: 6 }, () => [
          h(VCard, { class: 'rounded-lg', variant: 'outlined' }, () => [
            h(VCardText, null, () => [
              h(VList, { density: 'compact' }, () => [
                h(VListItem, { prependIcon: 'mdi-star' }, () => [
                  h(VListItemTitle, null, () => '\u63D0\u793A'),
                  h(VListItemSubtitle, null, () => '\u4F7F\u7528\u4FA7\u680F\u5BFC\u822A\u5FEB\u901F\u8BBF\u95EE\u5404\u529F\u80FD\u6A21\u5757')
                ]),
                h(VListItem, { prependIcon: 'mdi-palette' }, () => [
                  h(VListItemTitle, null, () => '\u81EA\u5B9A\u4E49'),
                  h(VListItemSubtitle, null, () => '\u53EF\u4FEE\u6539\u524D\u7AEF\u6E90\u7801\u81EA\u5B9A\u4E49\u6B64\u9875\u9762\u5185\u5BB9')
                ]),
                h(VListItem, { prependIcon: 'mdi-github' }, () => [
                  h(VListItemTitle, null, () => '\u5F00\u6E90'),
                  h(VListItemSubtitle, null, () => '\u524D\u7AEF\u6E90\u7801\u4F4D\u4E8E frontend/ \u76EE\u5F55')
                ])
              ])
            ])
          ])
        ])
      ]);

      // Footer
      const footer = h(VCard, {
        class: 'mt-6 rounded-lg',
        variant: 'flat',
        color: 'surface-variant'
      }, () => [
        h(VCardText, { class: 'text-center text-caption text-medium-emphasis pa-3' }, () => [
          h(VIcon, { size: 'small', class: 'mr-1' }, () => 'mdi-heart'),
          'MoviePilot CustomPage Plugin v1.0 | Powered by Vue 3 + Vuetify + Module Federation'
        ])
      ]);

      return h(VContainer, { fluid: true, class: 'pa-4' }, () => [
        welcomeBanner,
        navHeader,
        navCards,
        sysHeader,
        sysInfoRow,
        footer
      ]);
    };
  }
};

export default AppPage;
