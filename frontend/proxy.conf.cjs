module.exports = {
  "/api/**": {
    target: "http://127.0.0.1:8000",
    secure: false,
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ""),
  },
};
