ITERATION

❯ remove the presence of cities, it makes the system bug and remove htis "OpenStreetMap © CARTO | MapLibre", I just want to see the map.

ITERATION

go to visualizer/

- I want you to extract the information for the data/humans_clean.sqlite3, just extract what you need, you can take it in consolidate_database/ for individuals.
- There is a white gap between the maps and the section with information on the polity. Remove this gap, put the section with the polity higher.
- I don't want cumulative individuals, but the number of individuals every 50 years, where individuals get assigned. If your impact year is 1249, then you should be 1225 but if you are 1214, then you should be 1200

- the filter does not filter the table

- for the roma,n empire, the eastern Wu, The Han dynsaty, the sasain empire, when I click I get Nothin, how come ?

- Show the top 20 occupations.

go to visualizer/

❯ I want to see all the occupations name on the y axis. And the flter still does not work when I click on an occupation or  the date, the table does not filter

SAVE TO GiT

go to visualizer/

Add a filter where when I cluck on an occupaiton on the graphs, then I can see the table on theright that alsi gets filtered. Make sure that wxorks well, i need to see isually the new table. for some reaosns, when I asked you bfore it did not work, the table who nbot filter. and it looks like a difficultu problem to overcome

- add an option (a button) when I click, I can see the globe.

- Add a header and a bottom with a random logo; Add a about section where you talked about the project.

- add a legend (number of indivuals) on the y axis of the graph

ITERATION:

- Put the slider under the map and also a way to enter a date

- add a small arrow to go to the next step in time

SAVED TO GiT

- the globe does not work

- make sure the dataset is filtered. it still does not wrok, rethinkl the back-end if needed

Chnage int he databse

- there is an issue with the different levels (I need to add those in the dataset and fix that bug)
- For the impact year, add the real ipact year, not the round one

- make a button wheree when I click, the color of the politirs represent a log densoty of the numlber of individuals?

- add wirthout individuals with URL but without a date
- handle the hierarchies of polities
- add. ayear precision on the map

Save to git

02/03/2026

go to visualizer/

Extract the new data form the human_clean database. Now, an indiovudla cna be;ong to 2 polities at the same.

You cna see that sime polities are udolicates when they ahve the same name one is for instance (Roman Empire) is the other one is ROman empire and they ahve exactly the same number of idnivudals (as see in cliopatria_polites). If they ahev not if means, that the () polities is a hierarchical polities, whihc is an informauton you can find in cliopatria_data/processing/data/cliopatria.db.

I want you to add an option to swicth from aheirarchy to another on the map. But the defautls is the sammler hierarhcy.

Reaasign the individuals toi their polity, keeop the same overall design.

SAVE TO GIT

1) Can you add the real impact date of the indivuals. and on the map, I want to have the precise dates and when I click on next, I want to go to the next 25 years.

2) can you add the second level of polites as well

SAVE TO GIT
SAVE TO GIT

PROMPT 04/03/2026

Transfer the database to SUPABASE as the new endpoint. I want the same structure but just other service. the project is in .env

ITERATION

- Add the Globe as the defautl mode
- onlu add the polities with the lower levels, the more ggranular (forget abnout polities vs empire)s
- I want to be able to to put down the content of the polity, so that I have the mlapas full screen. When I click on a polity, then the content is coming up
- in the about, add the fatc that the data come from the Cuktrua Project and the Clippatira project. add an abiolity to search for a polity namle and enter.
- add the current dates rught at the bottom of the slider point

ITERATION

Iw ant the infromaiton to appear below the map when I clikc, not on the right

 ok, reduce a biut the widht of the tabel, so that the witdh of the 2 other table can be bigger.  make the information globale section a but less height, so that there is a
  but more for the map

Sart with the whole globe on the page centered at the roman empire in 200 AC
Add a little arrow or something to toggle down the infromation section (instead of the cross)

GIT SAVE

Remove the loading when I slide on the map, this is too short to need a loading informaiton

❯ in soruce, link this for the cliopatira project: <https://github.com/Seshat-Global-History-Databank/cliopatria>, for the cultrua daatabse, link this:
  <https://github.com/charlesdedampierre/cultura>

ITERATION

Can you make sure the slider goes up to 2024 ?

When is earch a polity, I d'ont want to see the () polity appears, becaude they are not showed in the map

and remove the POLITY metadata, because they are all "Polity"

add a little search on the tbale to search for an indovudla name

remove the different pagination for the Notable Individuals
 (otherwie the search does not work)

make sure the date on thte tbalke filter in the exact impact year

❯ the searh does not work on all idnviduals, can't younloadd all the idviudal directly ?

GIT SAVE

for the fame, Add 1 to all of them (0 shoudl become 1)

GIT SAVE

Can yoiu amek ti so that we see the name of the polity of the map directly. First with the bigger polities and the when we move we start to see the samller ones ?

GIT SAVE

Add the top cities

add an impact years range (from 25 to 70 years)
add the indovudla in the lsit that do not have a date
check hubetr de dapierr issues

change the round in the graph

make the slider quikcer
