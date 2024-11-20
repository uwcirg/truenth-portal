module.exports = {
  "presets": [
    ["@babel/env", {
      "modules": false,
      "useBuiltIns": "usage",
      "corejs": 2
    }]
  ],
  "plugins": [
    "@babel/plugin-syntax-dynamic-import",
    "@babel/plugin-transform-regenerator",
    ["@babel/plugin-transform-runtime",
     {
        "helpers": true,
        "regenerator": true
     }
    ]
  ]
}

