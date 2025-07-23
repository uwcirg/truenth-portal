/*
 * for DEVELOPMENT
 * run relevant npm script e.g. [npm run develop:js] when developing as any change will trigger a rebuild of the modified(files)
 */
const path = require("path");
module.exports = {
  extends: [path.resolve(__dirname, "./webpack.config.js")],
  watch: true,
  watchOptions: {
    aggregateTimeout: 300,
    poll: 1000,
    ignored: /node_modules/,
  },
  devtool: "eval",
};
