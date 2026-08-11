// firebase-config.js — add Firestore

const firebaseConfig = {
  apiKey: "AIzaSyAxLKESd2iu_PmCgxdcW6GNGGGc5BzQRVo",
  authDomain: "adaptlearn-94d97.firebaseapp.com",
  projectId: "adaptlearn-94d97",
  storageBucket: "adaptlearn-94d97.firebasestorage.app",
  messagingSenderId: "249065499457",
  appId: "1:249065499457:web:11dbfc7902a68247e68fc0",
  measurementId: "G-BBEGPHZ06B"
};

firebase.initializeApp(firebaseConfig);

// Auth — already existed
const auth = firebase.auth();

// Firestore — NEW
const db = firebase.firestore();