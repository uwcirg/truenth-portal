/*
 * for DEVELOPMENT
 * run relevant npm script e.g. [npm run develop:js] when developing as any change will trigger a rebuild of the modified(files)
 */
const path = require("path");
module.exports = {
  extends: [
    path.resolve(__dirname, './webpack.config.js'),
  ],
  devtool: "inline-source-map",
};
