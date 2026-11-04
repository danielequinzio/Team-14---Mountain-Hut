// All the text shown on the landing page lives in this file.
//
// PLACEHOLDER CONTENT: the hut name, numbers, routes, places and contact
// details below are invented so the page looks complete. Replace them with
// the real hut information; no other file needs to change.

export const hut = {
  name: "Rifugio Alpe Serena",
  region: "Western Alps, Piedmont, Italy",
  tagline: "Warm meals, shared tables and a safe stop high in the Alps.",

  intro:
    "Our hut is a place to eat, rest and recharge, whether you are on a day trip, " +
    "crossing the mountains over several days, or simply waiting for the weather " +
    "to clear. Meals are served at shared tables, and booking ahead helps us " +
    "prepare for every party.",

  facts: [
    { label: "Altitude", value: "2,150 m" },
    { label: "Open", value: "June – September" },
    { label: "Meals", value: "Lunch & dinner, by booking" },
    { label: "Extras", value: "E-bike charging" },
  ],

  offers: [
    {
      title: "Mountain meals",
      text: "Hearty local dishes served at shared tables, with set meal times you can plan your day around.",
    },
    {
      title: "Shelter & rest",
      text: "A warm place to stop when the weather turns, the day runs long or plans change.",
    },
    {
      title: "Dietary needs",
      text: "Tell us about allergies and dietary requirements when you book, so your meal is prepared safely.",
    },
    {
      title: "E-bike charging",
      text: "Top up your battery while you eat and enjoy the view.",
    },
  ],

  steps: [
    {
      title: "Check availability",
      text: "Pick a date and see which meal times still have seats. No account needed.",
    },
    {
      title: "Create an account",
      text: "Register once as a hiker, or log in if you already have an account.",
    },
    {
      title: "Book your table",
      text: "Choose a time and party size and receive a confirmation by email.",
    },
  ],

  routes: [
    {
      tag: "On foot",
      title: "From the valley",
      detail:
        "About 3 h 30 min and 900 m of climbing from the Pian Verde car park, following trail no. 12.",
    },
    {
      tag: "By car",
      title: "To the trailhead",
      detail:
        "Drive to the Pian Verde car park (1,250 m) and continue on foot. Parking fills up on summer weekends.",
    },
    {
      tag: "Public transport",
      title: "Train and bus",
      detail:
        "Take the regional train to the valley station, then the local bus to Pian Verde (summer timetable only).",
    },
  ],

  attractions: [
    {
      title: "Lago Sereno",
      time: "25 min",
      text: "A small alpine lake just above the hut, perfect for a short walk before or after your meal.",
    },
    {
      title: "Punta Aurora viewpoint",
      time: "1 h 15 min",
      text: "A panoramic summit with views over the surrounding peaks and glaciers.",
    },
    {
      title: "Old mule track",
      time: "40 min",
      text: "A historic path once used to carry supplies up to the pastures.",
    },
  ],

  contact: {
    address: "Località Pian Verde, Piedmont, Italy",
    phone: "+39 000 000 0000",
    email: "info@alpe-serena.example",
  },
};
