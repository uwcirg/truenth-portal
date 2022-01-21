const merge = require("webpack-merge").merge;
const common = require("./webpack.common.js");
/*
* for DEPLOYMENT
* when ready to deploy/push changes, run relevant npm script e.g. [npm run build:js]  webpack will bundle the code and apply optimizations e.g. uglify code, chunkify code
*/
module.exports = merge(common, {
  mode: "production"
});
