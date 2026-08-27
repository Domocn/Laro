#!/usr/bin/env python3
"""Compile compact event tuples into src/data/events.json."""
from __future__ import annotations

import json
from pathlib import Path

# (day, stage, start, end, title, kind)
# kind: music | comedy | food | family | talk | workshop | other
EVENTS = [
    # Friday Main Stage
    ("fri", "Main Stage", "13:45", "14:15", "Fiona-Lee", "music"),
    ("fri", "Main Stage", "14:45", "15:15", "Jerub", "music"),
    ("fri", "Main Stage", "15:45", "16:15", "The Ordinary Boys", "music"),
    ("fri", "Main Stage", "16:45", "17:15", "Meek", "music"),
    ("fri", "Main Stage", "17:45", "18:30", "White Lies", "music"),
    ("fri", "Main Stage", "19:00", "19:30", "Antony Szmierek", "music"),
    ("fri", "Main Stage", "20:00", "20:45", "Perrie", "music"),
    ("fri", "Main Stage", "21:15", "22:45", "Basement Jaxx", "music"),
    # Friday Cheese Hub
    ("fri", "Alex James' Cheese Hub", "14:15", "15:00", "Sable's Birthday Mix with Alex James", "music"),
    ("fri", "Alex James' Cheese Hub", "15:00", "16:30", "Nelson Ryecroft", "music"),
    ("fri", "Alex James' Cheese Hub", "16:30", "20:30", "Fort Green Takeover ft Geronimo, RJD, Sofa, Masqunada Brothers & LoopDeeLoop", "music"),
    ("fri", "Alex James' Cheese Hub", "20:30", "22:00", "Jamz Supernova", "music"),
    ("fri", "Alex James' Cheese Hub", "22:15", "00:15", "DJ Spoony", "music"),
    # Friday Outpost
    ("fri", "The Outpost", "12:00", "12:45", "Beato Burrito", "music"),
    ("fri", "The Outpost", "13:15", "14:00", "Jack Ride Out", "music"),
    ("fri", "The Outpost", "14:30", "15:15", "Maya Lane", "music"),
    ("fri", "The Outpost", "15:45", "16:30", "Jonny Morgan & The Moral Support", "music"),
    ("fri", "The Outpost", "17:00", "18:00", "Gospeloke", "music"),
    ("fri", "The Outpost", "18:30", "19:30", "The In-Here Brothers", "music"),
    ("fri", "The Outpost", "20:00", "21:00", "Hip Hop House Band", "music"),
    ("fri", "The Outpost", "21:30", "22:30", "Disco Ceilidh", "music"),
    ("fri", "The Outpost", "22:45", "00:15", "The Allergies", "music"),
    # Friday Big Kitchen
    ("fri", "The Big Kitchen", "13:30", "14:00", "Alex James, Flava Dave & The Cheese Hub Gang", "food"),
    ("fri", "The Big Kitchen", "14:30", "15:00", "James Graham", "food"),
    ("fri", "The Big Kitchen", "15:30", "16:00", "Jon Watts", "food"),
    ("fri", "The Big Kitchen", "16:30", "17:00", "Poppy O'Toole", "food"),
    # Friday Exchange
    ("fri", "The Exchange", "13:00", "14:00", "The Rubbish Shakespeare Company presents Romeo & Juliet", "comedy"),
    ("fri", "The Exchange", "14:30", "15:30", "You Okay Hun? Quiz", "talk"),
    ("fri", "The Exchange", "16:00", "16:30", "Improv Comedy Show", "comedy"),
    ("fri", "The Exchange", "16:45", "17:15", "Daniel Foxx", "comedy"),
    ("fri", "The Exchange", "17:30", "18:00", "Harriet Kemsley", "comedy"),
    ("fri", "The Exchange", "18:15", "18:45", "Ivo Graham", "comedy"),
    ("fri", "The Exchange", "19:30", "23:45", "Silent Disco (Fri)", "other"),
    # Friday Barn
    ("fri", "The Barn", "12:30", "13:00", "Sofar Sounds presents Ouraa", "music"),
    ("fri", "The Barn", "13:30", "14:00", "Sofar Sounds presents Dan Pye", "music"),
    ("fri", "The Barn", "14:30", "15:00", "Sofar Sounds presents Edbl", "music"),
    ("fri", "The Barn", "15:30", "16:15", "Big Smoke Brass: Back to the Noughties", "music"),
    ("fri", "The Barn", "16:45", "19:00", "The Whitney Soul Club – Northern Soul Session", "music"),
    # Friday Big Top
    ("fri", "The Big Top", "11:30", "12:00", "Mini Disco Divas Dance Party", "family"),
    ("fri", "The Big Top", "12:15", "12:30", "Gabby's Dollhouse Storytime (1)", "family"),
    ("fri", "The Big Top", "13:00", "13:45", "Tales of Beatrix Potter", "family"),
    ("fri", "The Big Top", "14:15", "14:30", "Gabby's Dollhouse Storytime (2)", "family"),
    ("fri", "The Big Top", "14:45", "15:15", "Mini Rhythm Makers Drumming Workshop", "family"),
    ("fri", "The Big Top", "15:30", "15:45", "Gabby's Dollhouse Storytime (3)", "family"),
    ("fri", "The Big Top", "16:15", "17:00", "Superhero Science Live!", "family"),
    ("fri", "The Big Top", "18:45", "19:00", "Special Guest Bedtime Stories", "family"),
    # Friday Saloon
    ("fri", "The Saloon", "12:00", "12:45", "Breakthrough Acoustic Set – Fri (1)", "music"),
    ("fri", "The Saloon", "13:15", "14:00", "Jack Banting", "music"),
    ("fri", "The Saloon", "14:30", "15:15", "Breakthrough – Fri (1)", "music"),
    ("fri", "The Saloon", "15:45", "17:15", "Kenny & Dolly: Country Legends", "music"),
    ("fri", "The Saloon", "17:45", "18:30", "Breakthrough – Fri (2)", "music"),
    ("fri", "The Saloon", "19:00", "19:45", "Inferno DJs – Fri", "music"),
    ("fri", "The Saloon", "20:15", "21:00", "Breakthrough – Fri (3)", "music"),
    ("fri", "The Saloon", "22:45", "00:15", "Breakthrough Acoustic Set – Fri (2)", "music"),
    # Friday Fire Pit
    ("fri", "The Fire Pit", "12:30", "13:00", "Christina Soteriou", "food"),
    ("fri", "The Fire Pit", "13:45", "14:15", "Josh Eggleton: The Pony", "food"),
    ("fri", "The Fire Pit", "15:00", "15:30", "Duncan Robertson & Kyu Jeon", "food"),
    ("fri", "The Fire Pit", "16:30", "17:00", "Cai Ap Bryn with Game and Flames", "food"),
    ("fri", "The Fire Pit", "19:00", "20:30", "MatBlak x The Pony (Josh Eggleton)", "food"),
    # Friday Campervan
    ("fri", "Campervan Live Lounge", "16:00", "17:00", "Joseph Lofthouse", "music"),
    ("fri", "Campervan Live Lounge", "17:00", "18:00", "Hannigan", "music"),
    ("fri", "Campervan Live Lounge", "18:00", "19:00", "Kavalla", "music"),
    ("fri", "Campervan Live Lounge", "23:00", "00:00", "Unplugged Jam", "music"),
    # Friday Chef's Pantry
    ("fri", "The Chef's Pantry", "12:00", "12:30", "The Ultimate Picnic Potato Salad with Poppy O'Toole", "workshop"),
    ("fri", "The Chef's Pantry", "13:15", "13:45", "The Ultimate Salad with Jon Watts", "workshop"),
    ("fri", "The Chef's Pantry", "14:30", "15:00", "Wildfarmed's Crumpet Club", "workshop"),
    ("fri", "The Chef's Pantry", "15:45", "16:15", "Umami, Crunch & Contrast with Christina Soteriou", "workshop"),
    ("fri", "The Chef's Pantry", "17:00", "17:30", "Oi Kimchi with Duncan & Kyu from Bokman's", "workshop"),
    # Friday Table Sessions
    ("fri", "Table Sessions", "11:00", "12:00", "Session sign-ups", "workshop"),
    ("fri", "Table Sessions", "12:00", "12:30", "Pact Coffee", "workshop"),
    ("fri", "Table Sessions", "13:15", "13:45", "Masterclasses with Project-D", "workshop"),
    ("fri", "Table Sessions", "14:30", "15:00", "Pop & Pour with Bordeaux Wines", "workshop"),
    ("fri", "Table Sessions", "15:45", "16:15", "St-Germain", "workshop"),
    ("fri", "Table Sessions", "17:00", "17:30", "Champagne Canard-Duchêne", "workshop"),
    # Friday Book Signing
    ("fri", "Book Signing", "13:05", "13:30", "Christina Soteriou", "talk"),
    ("fri", "Book Signing", "16:05", "16:30", "Jon Watts", "talk"),
    ("fri", "Book Signing", "17:05", "17:30", "Poppy O'Toole", "talk"),

    # Saturday Main Stage
    ("sat", "Main Stage", "12:00", "12:40", "Justin Fletcher", "family"),
    ("sat", "Main Stage", "13:15", "13:45", "She's in Parties", "music"),
    ("sat", "Main Stage", "14:15", "14:45", "Bradley Simpson", "music"),
    ("sat", "Main Stage", "15:15", "15:45", "Ms. Dynamite", "music"),
    ("sat", "Main Stage", "16:15", "17:00", "The Cuban Brothers", "music"),
    ("sat", "Main Stage", "17:30", "18:00", "Tors", "music"),
    ("sat", "Main Stage", "18:30", "19:15", "Mimi Webb", "music"),
    ("sat", "Main Stage", "19:45", "20:45", "Rudim3ntal", "music"),
    ("sat", "Main Stage", "21:15", "22:55", "The Streets", "music"),
    # Saturday Cheese Hub
    ("sat", "Alex James' Cheese Hub", "11:00", "12:00", "Alex James Hub Quiz", "talk"),
    ("sat", "Alex James' Cheese Hub", "13:00", "14:30", "DJ Dan (Propaganda)", "music"),
    ("sat", "Alex James' Cheese Hub", "14:30", "16:30", "Geronimo", "music"),
    ("sat", "Alex James' Cheese Hub", "17:00", "18:00", "Chris Stark – DJ set", "music"),
    ("sat", "Alex James' Cheese Hub", "18:15", "19:15", "Katya & Friends", "music"),
    ("sat", "Alex James' Cheese Hub", "19:30", "20:45", "Pips Taylor", "music"),
    ("sat", "Alex James' Cheese Hub", "21:00", "22:30", "Connor Coates", "music"),
    ("sat", "Alex James' Cheese Hub", "22:45", "00:15", "Sarah Story", "music"),
    # Saturday Outpost
    ("sat", "The Outpost", "11:00", "11:45", "Disco Divas Dance Workout", "other"),
    ("sat", "The Outpost", "12:15", "13:00", "Ben Brown", "music"),
    ("sat", "The Outpost", "13:30", "14:00", "Marley", "music"),
    ("sat", "The Outpost", "14:30", "15:15", "Ines Rae", "music"),
    ("sat", "The Outpost", "15:45", "16:45", "Duke", "music"),
    ("sat", "The Outpost", "17:15", "18:00", "Riding the Low", "music"),
    ("sat", "The Outpost", "18:30", "19:30", "Grohlercoaster", "music"),
    ("sat", "The Outpost", "20:00", "21:00", "Barrioke", "music"),
    ("sat", "The Outpost", "21:15", "22:30", "Ed Travers DJ set", "music"),
    ("sat", "The Outpost", "22:45", "00:15", "Revival House Project", "music"),
    # Saturday Big Kitchen
    ("sat", "The Big Kitchen", "11:30", "12:00", "Sophie Wyburd with Country Life", "food"),
    ("sat", "The Big Kitchen", "12:30", "13:00", "Amber Francis", "food"),
    ("sat", "The Big Kitchen", "13:30", "14:00", "Anna Haugh", "food"),
    ("sat", "The Big Kitchen", "14:30", "15:00", "Rachel Allen", "food"),
    ("sat", "The Big Kitchen", "15:30", "16:00", "Nokx Majozi", "food"),
    ("sat", "The Big Kitchen", "16:30", "17:00", "Tom Barnes", "food"),
    # Saturday Exchange
    ("sat", "The Exchange", "12:00", "12:45", "Big Feastival's Big Quiz", "talk"),
    ("sat", "The Exchange", "13:15", "14:00", "Joe and James Fact Up Podcast", "talk"),
    ("sat", "The Exchange", "14:30", "15:30", "The Scummy Mummies show", "comedy"),
    ("sat", "The Exchange", "16:00", "16:45", "The Traitors Improv Show", "comedy"),
    ("sat", "The Exchange", "17:45", "18:15", "Shappi Khorsandi", "comedy"),
    ("sat", "The Exchange", "18:30", "19:00", "Suzi Ruffell", "comedy"),
    ("sat", "The Exchange", "19:30", "23:45", "Silent Disco (Sat)", "other"),
    # Saturday Barn
    ("sat", "The Barn", "12:30", "13:00", "Sofar Sounds presents Jessie Malcolm", "music"),
    ("sat", "The Barn", "13:30", "14:00", "Sofar Sounds presents Darcey Salt", "music"),
    ("sat", "The Barn", "14:30", "15:00", "Sofar Sounds presents Yaz", "music"),
    ("sat", "The Barn", "15:15", "16:00", "Piano-oke", "music"),
    ("sat", "The Barn", "16:30", "17:30", "Kilne", "music"),
    ("sat", "The Barn", "18:00", "19:00", "King Cerulean", "music"),
    # Saturday Big Top
    ("sat", "The Big Top", "10:30", "11:00", "Morning Dance Party – K-Pop Demon Hunters Disco", "family"),
    ("sat", "The Big Top", "11:30", "12:00", "Mini Rhythm Makers Drumming Workshop", "family"),
    ("sat", "The Big Top", "12:30", "13:15", "Big Beats & Little Feet Family Disco", "family"),
    ("sat", "The Big Top", "13:45", "14:15", "MC Grammar", "family"),
    ("sat", "The Big Top", "14:45", "15:45", "The Selfish Giant", "family"),
    ("sat", "The Big Top", "16:15", "17:00", "Street Dance Workshop", "family"),
    ("sat", "The Big Top", "17:30", "18:30", "Musical Bingo", "family"),
    ("sat", "The Big Top", "18:45", "19:00", "Special Guest Bedtime Stories", "family"),
    # Saturday Saloon
    ("sat", "The Saloon", "10:30", "11:15", "Kieran Ferrier", "music"),
    ("sat", "The Saloon", "11:45", "12:30", "Breakthrough Acoustic Set – Sat (1)", "music"),
    ("sat", "The Saloon", "13:00", "13:45", "Breakthrough – Sat (2)", "music"),
    ("sat", "The Saloon", "14:15", "15:00", "Connor McGrath", "music"),
    ("sat", "The Saloon", "16:00", "16:45", "Bradley Simpson Presents: The Open Arms Popup", "music"),
    ("sat", "The Saloon", "17:45", "18:30", "Breakthrough – Sat (2)", "music"),
    ("sat", "The Saloon", "19:00", "19:45", "Inferno DJs – Sat", "music"),
    ("sat", "The Saloon", "20:15", "21:00", "Breakthrough – Sat (3)", "music"),
    ("sat", "The Saloon", "21:15", "22:30", "The Modern Kind", "music"),
    ("sat", "The Saloon", "22:45", "00:15", "Breakthrough Acoustic Set – Sat (2)", "music"),
    # Saturday Fire Pit
    ("sat", "The Fire Pit", "12:00", "12:30", "MatBlak", "food"),
    ("sat", "The Fire Pit", "13:15", "13:45", "Asim Merali: Goldies", "food"),
    ("sat", "The Fire Pit", "14:30", "15:00", "Bab Haus with Leyli Homayoonfar", "food"),
    ("sat", "The Fire Pit", "15:45", "16:15", "Diotima Vila with The Dragon Flame", "food"),
    ("sat", "The Fire Pit", "17:00", "17:30", "Murf with The Beefy Boys", "food"),
    ("sat", "The Fire Pit", "19:00", "20:30", "MatBlak x Goldie's Asim Merali", "food"),
    # Saturday Campervan
    ("sat", "Campervan Live Lounge", "16:00", "17:00", "Sorrel", "music"),
    ("sat", "Campervan Live Lounge", "17:00", "18:00", "Samuel Ashton", "music"),
    ("sat", "Campervan Live Lounge", "18:00", "19:00", "Laura Silverstone", "music"),
    ("sat", "Campervan Live Lounge", "23:00", "00:00", "Unplugged Jam", "music"),
    # Saturday Chef's Pantry
    ("sat", "The Chef's Pantry", "10:30", "11:00", "Wildfarmed's Crumpet Club", "workshop"),
    ("sat", "The Chef's Pantry", "11:30", "12:00", "Peppermint Crisp Tarts with Nokx Majozi", "workshop"),
    ("sat", "The Chef's Pantry", "12:45", "13:15", "Q&A with Tom Barnes", "workshop"),
    ("sat", "The Chef's Pantry", "14:00", "14:30", "Capturing the Season: Create Your Own Finishing Salt with Amber Francis", "workshop"),
    ("sat", "The Chef's Pantry", "15:15", "15:45", "Anna Haugh's Courgette Salad", "workshop"),
    ("sat", "The Chef's Pantry", "16:30", "17:00", "Picnic time with Rachel Allen", "workshop"),
    # Saturday Table Sessions
    ("sat", "Table Sessions", "10:00", "11:00", "Session sign-ups", "workshop"),
    ("sat", "Table Sessions", "11:30", "12:00", "St-Germain", "workshop"),
    ("sat", "Table Sessions", "12:45", "13:15", "Tiny Rebel presents Rebel Bingo", "workshop"),
    ("sat", "Table Sessions", "14:00", "14:30", "Chapel Down", "workshop"),
    ("sat", "Table Sessions", "15:15", "15:45", "Farm-to-Skin Discovery Workshop with Tarro Skincare", "workshop"),
    ("sat", "Table Sessions", "16:30", "17:00", "Champagne Canard-Duchêne", "workshop"),
    # Saturday Book Signing
    ("sat", "Book Signing", "14:05", "14:30", "Anna Haugh", "talk"),
    ("sat", "Book Signing", "15:05", "15:30", "Adam Henson", "talk"),
    ("sat", "Book Signing", "16:05", "16:30", "Nokx Majozi", "talk"),
    ("sat", "Book Signing", "17:05", "17:30", "Murf – The Beefy Boys", "talk"),
    ("sat", "Book Signing", "17:15", "17:45", "Martyn Odell", "talk"),

    # Sunday Main Stage
    ("sun", "Main Stage", "13:15", "13:45", "The Rosadocs", "music"),
    ("sun", "Main Stage", "14:15", "15:00", "Nubiyan Twist", "music"),
    ("sun", "Main Stage", "15:30", "16:00", "Red Rum Club", "music"),
    ("sun", "Main Stage", "16:30", "17:15", "The Coral", "music"),
    ("sun", "Main Stage", "17:45", "18:30", "Freya Ridings", "music"),
    ("sun", "Main Stage", "19:00", "19:45", "Doves", "music"),
    ("sun", "Main Stage", "20:15", "21:45", "Bastille", "music"),
    # Sunday Cheese Hub
    ("sun", "Alex James' Cheese Hub", "11:00", "12:00", "Alex James Hub Quiz Sunday Special", "talk"),
    ("sun", "Alex James' Cheese Hub", "13:00", "17:30", "DJ Flack & The James Family Takeover ft Da Cheese Police", "music"),
    ("sun", "Alex James' Cheese Hub", "17:45", "19:15", "Simon Pegg", "music"),
    ("sun", "Alex James' Cheese Hub", "19:30", "22:45", "Syrup: Tall Paul B2B Seb Fontaine", "music"),
    # Sunday Outpost
    ("sun", "The Outpost", "11:15", "12:00", "Pop Party Dance Workout", "other"),
    ("sun", "The Outpost", "12:30", "13:15", "Das Brass", "music"),
    ("sun", "The Outpost", "13:45", "14:30", "Mia Kelly", "music"),
    ("sun", "The Outpost", "15:00", "16:00", "Noble Jacks", "music"),
    ("sun", "The Outpost", "17:45", "18:45", "DJ Noel Malaga's Indie Karaoke", "music"),
    ("sun", "The Outpost", "19:00", "20:00", "DJ Dials Davis 'Garage Warm Up'", "music"),
    ("sun", "The Outpost", "20:15", "21:00", "Sweet Female Attitude", "music"),
    ("sun", "The Outpost", "21:15", "22:45", "Fabio & Grooverider", "music"),
    # Sunday Big Kitchen
    ("sun", "The Big Kitchen", "11:30", "12:00", "Sharp's Brewery: Stephane Delourme", "food"),
    ("sun", "The Big Kitchen", "12:30", "13:00", "Meera Sodha", "food"),
    ("sun", "The Big Kitchen", "13:30", "14:00", "Emily English", "food"),
    ("sun", "The Big Kitchen", "14:30", "15:00", "Sally Abé", "food"),
    ("sun", "The Big Kitchen", "15:30", "16:00", "Simon Rogan", "food"),
    ("sun", "The Big Kitchen", "16:30", "17:00", "Edd Kimber (TheBoyWhoBakes)", "food"),
    ("sun", "The Big Kitchen", "16:30", "17:15", "The Horne Section", "comedy"),
    # Sunday Exchange
    ("sun", "The Exchange", "11:15", "12:45", "Big Feastival's Got Talent", "other"),
    ("sun", "The Exchange", "13:15", "14:15", "Taskmaster Club", "talk"),
    ("sun", "The Exchange", "14:45", "15:45", "The Scummy Mummies Podcast with Em Clarkson", "comedy"),
    ("sun", "The Exchange", "16:00", "16:45", "Play Your Charts Right", "talk"),
    ("sun", "The Exchange", "17:00", "17:30", "Kyrah Gray", "comedy"),
    ("sun", "The Exchange", "17:45", "18:15", "Scott Bennett", "comedy"),
    ("sun", "The Exchange", "18:30", "19:00", "Joel Dommett", "comedy"),
    ("sun", "The Exchange", "19:30", "22:45", "Silent Disco (Sun)", "other"),
    # Sunday Barn
    ("sun", "The Barn", "11:15", "12:00", "Big Brass Energy with Das Brass", "music"),
    ("sun", "The Barn", "12:30", "13:00", "Sofar Sounds presents Krystyn", "music"),
    ("sun", "The Barn", "13:30", "14:00", "Sofar Sounds presents Drleosol", "music"),
    ("sun", "The Barn", "14:30", "15:00", "Daisy Veacock", "music"),
    ("sun", "The Barn", "15:45", "16:45", "Big Feastival Barn Dance", "music"),
    ("sun", "The Barn", "17:45", "18:30", "Sunday Singalong with James Bradshaw", "music"),
    # Sunday Big Top
    ("sun", "The Big Top", "10:30", "11:00", "Nursery Rhyme Time", "family"),
    ("sun", "The Big Top", "11:30", "12:30", "Taskmaster Club Mini", "family"),
    ("sun", "The Big Top", "13:00", "14:00", "Maddie Moate's Big Honeybee Bash", "family"),
    ("sun", "The Big Top", "14:30", "15:15", "School of Beatbox Performance", "family"),
    ("sun", "The Big Top", "15:15", "15:45", "School of Beatbox Workshop", "family"),
    ("sun", "The Big Top", "16:15", "17:00", "Nick Cope Singalong", "family"),
    ("sun", "The Big Top", "17:30", "18:15", "Mini Rhythm Makers Drumming Workshop", "family"),
    ("sun", "The Big Top", "18:30", "18:45", "Special Guest Bedtime Stories", "family"),
    # Sunday Saloon
    ("sun", "The Saloon", "10:30", "11:15", "Kieran Ferrier", "music"),
    ("sun", "The Saloon", "11:45", "12:30", "Breakthrough Acoustic Set – Sun (1)", "music"),
    ("sun", "The Saloon", "13:00", "13:45", "Inferno DJs", "music"),
    ("sun", "The Saloon", "14:00", "14:45", "Stomp & Shuffle Line Dancing", "music"),
    ("sun", "The Saloon", "16:00", "16:45", "Breakthrough", "music"),
    ("sun", "The Saloon", "17:00", "17:30", "Kieran Ferrier Solo Acoustic", "music"),
    ("sun", "The Saloon", "17:45", "18:30", "Breakthrough", "music"),
    ("sun", "The Saloon", "19:00", "19:45", "Breakthrough", "music"),
    ("sun", "The Saloon", "20:15", "21:00", "Kieran Ferrier", "music"),
    ("sun", "The Saloon", "21:30", "22:15", "Breakthrough Acoustic Set", "music"),
    # Sunday Fire Pit
    ("sun", "The Fire Pit", "12:00", "12:30", "Melanie Brown", "food"),
    ("sun", "The Fire Pit", "13:15", "13:45", "MatBlak", "food"),
    ("sun", "The Fire Pit", "14:30", "15:00", "Freddy Bird: The Little French", "food"),
    ("sun", "The Fire Pit", "15:45", "16:15", "Matt Jefferies with The Woozy Pig", "food"),
    ("sun", "The Fire Pit", "17:00", "17:30", "Stewart Parker with The Larder House", "food"),
    ("sun", "The Fire Pit", "18:30", "20:00", "MatBlak x The Laundry's Melanie Brown", "food"),
    # Sunday Campervan
    ("sun", "Campervan Live Lounge", "16:00", "17:00", "Doad", "music"),
    ("sun", "Campervan Live Lounge", "17:00", "18:00", "Run Remedy", "music"),
    ("sun", "Campervan Live Lounge", "18:00", "19:00", "Tom Dibb", "music"),
    ("sun", "Campervan Live Lounge", "22:00", "23:00", "Unplugged Jam", "music"),
    # Sunday Chef's Pantry
    ("sun", "The Chef's Pantry", "11:30", "12:00", "Meera Sodha's No-Cook Chickpea, Tomato and Cucumber Salad", "workshop"),
    ("sun", "The Chef's Pantry", "12:45", "13:15", "Q&A with Simon Rogan", "workshop"),
    ("sun", "The Chef's Pantry", "14:00", "14:30", "Chocolate Tasting and Truffle Making with Edd Kimber", "workshop"),
    ("sun", "The Chef's Pantry", "15:15", "15:45", "Nutrition Myths Q&A with Emily English", "workshop"),
    ("sun", "The Chef's Pantry", "16:30", "17:00", "A Very Berry British Trifle with Sally Abé", "workshop"),
    # Sunday Table Sessions
    ("sun", "Table Sessions", "10:00", "11:00", "Session sign-ups", "workshop"),
    ("sun", "Table Sessions", "11:30", "12:00", "Masterclasses with Project-D", "workshop"),
    ("sun", "Table Sessions", "12:45", "13:15", "Champagne Canard-Duchêne", "workshop"),
    ("sun", "Table Sessions", "14:00", "14:30", "Farm-to-Glass Cocktail Club with Warner's", "workshop"),
    ("sun", "Table Sessions", "15:15", "15:45", "Chapel Down", "workshop"),
    ("sun", "Table Sessions", "16:30", "17:00", "Pop & Pour with Bordeaux Wines", "workshop"),
    # Sunday Book Signing
    ("sun", "Book Signing", "13:05", "13:30", "Meera Sodha", "talk"),
    ("sun", "Book Signing", "14:05", "14:30", "Emily English", "talk"),
    ("sun", "Book Signing", "14:15", "14:45", "Maddie Moate", "talk"),
    ("sun", "Book Signing", "15:05", "15:30", "Sally Abé", "talk"),
    ("sun", "Book Signing", "16:05", "16:30", "Simon Rogan", "talk"),
]


def slug(s: str) -> str:
    out = []
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in " &'-/":
            out.append("-")
    while "--" in (joined := "".join(out)):
        out = list(joined.replace("--", "-"))
    return "".join(out).strip("-")


def main() -> None:
    events = []
    for i, (day, stage, start, end, title, kind) in enumerate(EVENTS, 1):
        events.append(
            {
                "id": f"{day}-{slug(stage)[:18]}-{start.replace(':', '')}-{slug(title)[:28]}-{i:03d}",
                "day": day,
                "stage": stage,
                "start": start,
                "end": end,
                "title": title,
                "kind": kind,
            }
        )
    dest = Path(__file__).resolve().parents[1] / "src" / "data" / "events.json"
    dest.write_text(json.dumps(events, indent=2) + "\n")
    print(f"wrote {len(events)} events to {dest}")


if __name__ == "__main__":
    main()
