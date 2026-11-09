export default {
  content: [
    "./index.html",
    "./application.html",
    "./public/lang.js",
    "./public/alidation.js",
  ],
  theme: {
    extend: {
      colors: {
        brasaPrimary: "#C2410C",
        brasaAccent: "#5CB66C",
        brasaInk: "#1F2937",
        brasaCream: "#FFF7ED",
      },
      fontFamily: {
        display: ["Sekuya", "Bebas Neue", "cursive"],
        sans: ["Inter", "sans-serif"],
      },
      backgroundImage: {
        ember:
          "radial-gradient(circle at top left, rgba(194,65,12,0.16), transparent 32%), radial-gradient(circle at bottom right, rgba(92,182,108,0.14), transparent 24%)",
      },
      boxShadow: {
        glow: "0 20px 60px rgba(194, 65, 12, 0.18)",
      },
    },
  },
  plugins: [],
};
