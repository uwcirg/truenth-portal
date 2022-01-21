const merge = require("webpack-merge").merge;
const common = require("./webpack.common.js");
/*
* for DEVELOPMENT
* run relevant npm script e.g. [npm run develop:js] when developing as any change will trigger a rebuild of the modified(files)
*/
module.exports = merge(common, {
  mode: "development"
});
