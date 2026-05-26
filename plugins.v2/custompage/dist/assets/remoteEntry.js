/**
 * CustomPage Module Federation Remote Entry
 * NOTE: This file is hand-crafted. Regenerate via `npm run build` in the
 * frontend/ directory when source changes, then copy dist/assets/ output here.
 */

const moduleMap = {
  './Page': () => import('./__federation_expose_Page.js'),
  './Config': () => import('./__federation_expose_Config.js'),
  './AppPage': () => import('./__federation_expose_AppPage.js')
};

const shared = {
  vue: {
    get: () => Promise.resolve().then(() => __federation_shared_vue()),
    loaded: 1,
    requiredVersion: false
  },
  vuetify: {
    get: () => Promise.resolve().then(() => __federation_shared_vuetify()),
    loaded: 1,
    requiredVersion: false
  }
};

let __federation_shared_vue;
let __federation_shared_vuetify;

const init = (shareScope) => {
  if (shareScope.vue) {
    const vueEntry = shareScope.vue;
    const vueVersions = Object.values(vueEntry);
    if (vueVersions.length > 0 && vueVersions[0].get) {
      __federation_shared_vue = vueVersions[0].get;
    } else {
      console.error('[CustomPage] shareScope.vue has no valid entries or missing get()');
    }
  } else {
    console.error('[CustomPage] shareScope.vue is missing from shared scope');
  }
  if (shareScope.vuetify) {
    const vuetifyEntry = shareScope.vuetify;
    const vuetifyVersions = Object.values(vuetifyEntry);
    if (vuetifyVersions.length > 0 && vuetifyVersions[0].get) {
      __federation_shared_vuetify = vuetifyVersions[0].get;
    } else {
      console.error('[CustomPage] shareScope.vuetify has no valid entries or missing get()');
    }
  } else {
    console.error('[CustomPage] shareScope.vuetify is missing from shared scope');
  }
};

const get = (module) => {
  if (!moduleMap[module]) {
    throw new Error(`Module ${module} does not exist in container.`);
  }
  return moduleMap[module];
};

export { init, get };
export default { init, get };
