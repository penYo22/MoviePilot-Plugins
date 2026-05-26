/**
 * CustomPage Module Federation Remote Entry
 * Generated for MoviePilot V2 Plugin system
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
    if (vueVersions.length > 0) {
      __federation_shared_vue = vueVersions[0].get;
    }
  }
  if (shareScope.vuetify) {
    const vuetifyEntry = shareScope.vuetify;
    const vuetifyVersions = Object.values(vuetifyEntry);
    if (vuetifyVersions.length > 0) {
      __federation_shared_vuetify = vuetifyVersions[0].get;
    }
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
