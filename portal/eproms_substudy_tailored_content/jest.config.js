module.exports = {
    preset: '@vue/cli-plugin-unit-jest',
    testPathIgnorePatterns: ['\\\\node_modules\\\\'],
    transformIgnorePatterns: ['./node_modules/'],
    moduleNameMapper: {
        "^[./a-zA-Z0-9$_-]+\\.(png|jpeg|tiff)$": "<rootDir>/src/__mocks__/fileMock.js",
        "^[./a-zA-Z0-9$_-]+\\.(css|less)$": "<rootDir>/src/__mocks__/styleMock.js",
        "^expose-loader+?": "<rootDir>/node_modules/expose-loader/dist/cjs.js"
    },
    verbose: false
}
