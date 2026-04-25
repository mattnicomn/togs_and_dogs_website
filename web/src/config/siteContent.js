/**
 * Centralized site content for Togs & Dogs.
 * Edit this file to update services, pricing, testimonials, and service areas.
 */

export const siteContent = {
  brandName: "Togs & Dogs",
  contactEmail: "hello@toganddogs.com",
  contactPhone: "(555) 123-4567",

  
  services: [
    {
      id: "walking",
      title: "Dog Walking",
      emoji: "🐕",
      description: "Perfect for energetic pups or those who just need a midday break. We provide exercise, fresh water, and lots of praise.",
      price: "Est. from $25",
      unit: "per walk",
      features: [
        "20, 30, or 45-minute walks",
        "Individual attention",
        "GPS tracked visits"
      ]
    },
    {
      id: "sitting",
      title: "Pet Sitting",
      emoji: "🐱",
      description: "Quality care in the comfort of your home. Ideal for cats, senior dogs, and small animals.",
      price: "Est. from $22",
      unit: "per visit",
      features: [
        "Feeding and fresh water",
        "Litter box / yard cleanup",
        "Administering medication"
      ]
    },
    {
      id: "overnight",
      title: "Overnight Stays",
      emoji: "🏡",
      description: "24/7 companionship for pets who thrive on constant company and a consistent routine.",
      price: "Est. from $85",
      unit: "per night",
      features: [
        "Maximum cuddle time",
        "Morning and evening walks",
        "Home security check"
      ]
    }
  ],

  testimonials: [
    {
      text: "The photo updates I get while at work are the highlight of my day! I know my dog is in great hands.",
      author: "Sample Client (and Buddy)"
    },
    {
      text: "Professional, reliable, and my cats loved them. Great peace of mind while we were away.",
      author: "Sample Client (and Whiskers)"
    },
    {
      text: "Highly recommend! The Meet & Greet made us feel so comfortable. Best pet service we've used.",
      author: "Sample Client (and Max)"
    }
  ],

  serviceAreas: {
    neighborhoods: [
      { name: "Downtown", status: "Primary" },
      { name: "West End", status: "Limited" },
      { name: "North Ridge", status: "Expanding Soon" }
    ],
    zipCodes: ["12345", "12346"],
    availability: "General service hours: 7 AM - 9 PM. Holiday care available upon request."
  }
};
