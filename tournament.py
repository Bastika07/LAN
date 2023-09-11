import sqlite3
import json

# Define the database schema
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,
    name TEXT
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY,
    team_a_id INTEGER,
    team_b_id INTEGER,
    round INTEGER,
    is_winner_bracket BOOLEAN,
    score_a INTEGER DEFAULT 0,
    score_b INTEGER DEFAULT 0,
    winner_id INTEGER DEFAULT NULL,  -- Add the winner_id column
    FOREIGN KEY (team_a_id) REFERENCES teams (id),
    FOREIGN KEY (team_b_id) REFERENCES teams (id)
);
"""
class TournamentDatabase:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.executescript(DB_SCHEMA)
        self.conn.commit()

    def insert_team(self, team_name):
        self.cursor.execute("INSERT INTO teams (name) VALUES (?)", (team_name,))
        self.conn.commit()

    def get_teams(self):
        self.cursor.execute("SELECT id, name FROM teams")
        return self.cursor.fetchall()

    def insert_match(self, team_a_name, team_b_name, round_number, is_winner_bracket):
        team_a_id = self.get_or_insert_team_id(team_a_name)
        team_b_id = self.get_or_insert_team_id(team_b_name)
        self.cursor.execute(
            "INSERT INTO matches (team_a_id, team_b_id, round, is_winner_bracket) VALUES (?, ?, ?, ?)",
            (team_a_id, team_b_id, round_number, is_winner_bracket),
        )
        self.conn.commit()

    def get_or_insert_team_id(self, team_name):
        self.cursor.execute("SELECT id FROM teams WHERE name=?", (team_name,))
        team_id = self.cursor.fetchone()
        if team_id is None:
            self.insert_team(team_name)
            return self.get_or_insert_team_id(team_name)
        return team_id[0]

    def get_matches_for_round(self, round_number, is_winner_bracket):
        self.cursor.execute(
            "SELECT id, team_a_id, team_b_id, round, is_winner_bracket, score_a, score_b, winner_id FROM matches WHERE round=? AND is_winner_bracket=?",
            (round_number, is_winner_bracket),
        )

        return self.cursor.fetchall()

    def get_team_names_for_match(self, match_id):
        self.cursor.execute(
            "SELECT t1.name, t2.name FROM matches "
            "INNER JOIN teams AS t1 ON matches.team_a_id = t1.id "
            "INNER JOIN teams AS t2 ON matches.team_b_id = t2.id "
            "WHERE matches.id = ?",
            (match_id,),
        )
        team_names = self.cursor.fetchone()
        return team_names
    
    def get_team_name_by_id(self, team_id):
        query = "SELECT name FROM teams WHERE id = ?"
        self.cursor.execute(query, (team_id,))
        result = self.cursor.fetchone()
        return result[0] if result else "Unknown Team"

    def update_match_result(self, match_id, score_a, score_b):
        self.cursor.execute(
            "UPDATE matches SET score_a=?, score_b=? WHERE id=?",
            (score_a, score_b, match_id),
        )
        self.conn.commit()

    def calculate_winner(self, match_id):
        self.cursor.execute("SELECT team_a_id, team_b_id, score_a, score_b FROM matches WHERE id=?", (match_id,))
        row = self.cursor.fetchone()
        if row:
            team_a_id, team_b_id, score_a, score_b = row
            if score_a > score_b:
                return team_a_id
            elif score_a < score_b:
                return team_b_id
        return None  # Match is undecided

    def get_results(self):
        results = {}
        self.cursor.execute("SELECT id, score_a, score_b FROM matches")
        rows = self.cursor.fetchall()
        for row in rows:
            match_id, score_a, score_b = row
            results[match_id] = (score_a, score_b)
        return results

class Tournament:

    def list_matches(self, round_number, is_winner_bracket):
        matches = self.db.get_matches_for_round(round_number, is_winner_bracket)
    
        if is_winner_bracket:
            bracket_type = "Winner Bracket"
        else:
            bracket_type = "Loser Bracket"

        print(f"Round {round_number} - {bracket_type}: True")

        for match in matches:
            match_id, team_a_id, team_b_id, score_a, score_b, winner_id, round_id, is_winner_bracket = match
        
            # Retrieve team names based on team_a_id and team_b_id
            team_a_name = self.db.get_team_name_by_id(team_a_id)
            team_b_name = self.db.get_team_name_by_id(team_b_id)
        
            # Retrieve the winner's name based on winner_id
            if winner_id is not None:
                winner_name = self.db.get_team_name_by_id(winner_id)
            else:
                winner_name = "Undecided"
        
            # Print the match details including team names and the winner's name
            print(f"Match {match_id}: {team_a_name} vs {team_b_name} - Score: {score_a} - {score_b} - Winner: {winner_name}")

    def __init__(self, db_file, config_file):
        self.db = TournamentDatabase(db_file)
        self.config = self.load_config(config_file)

    def load_config(self, config_file):
        with open(config_file, 'r') as f:
            return json.load(f)

    def insert_teams_from_config(self):
        for team_name in self.config.get("teams", []):
            self.db.insert_team(team_name)

    def generate_matches(self):
        teams = self.db.get_teams()
        num_teams = len(teams)

        if num_teams % 2 != 0:
            teams.append(("Bye",))  # Add a "Bye" team if the number of teams is odd

        rounds = num_teams - 1
        matches_per_round = num_teams // 2

        for round_number in range(1, rounds + 1):
            is_winner_bracket = True
            if round_number > rounds / 2:
                is_winner_bracket = False

            for match in range(1, matches_per_round + 1):
                team_a, team_b = teams[match - 1], teams[num_teams - match]
                self.db.insert_match(team_a[1], team_b[1], round_number, is_winner_bracket)

    def generate_single_elimination_next_round(self, round_number):
        matches = self.db.get_matches_for_round(round_number, is_winner_bracket=True)

        # Check if all previous round matches have winners
        if all(self.db.calculate_winner(match_id) for match_id, _, _, _, _, _, _ in matches):
            # Create the next round with half as many matches
            next_round = round_number + 1
            is_winner_bracket = True
            new_match_ids = []

            for i in range(0, len(matches), 2):
                team_a_name, team_b_name = self.db.get_team_names_for_match(matches[i][0]), self.db.get_team_names_for_match(matches[i + 1][0])
                self.db.insert_match(team_a_name, team_b_name, next_round, is_winner_bracket)
                new_match_ids.append(self.db.conn.lastrowid)

            print(f"Generated Round {next_round} - Winner Bracket: {is_winner_bracket}")
            for i, match_id in enumerate(new_match_ids):
                team_a_name, team_b_name = self.db.get_team_names_for_match(match_id)
                print(f"Match {match_id}: {team_a_name} vs {team_b_name}")

    def generate_double_elimination_next_round(self, round_number):
        winner_bracket_matches = self.db.get_matches_for_round(round_number, is_winner_bracket=True)
        loser_bracket_matches = self.db.get_matches_for_round(round_number, is_winner_bracket=False)

        # Check if all winner bracket matches have winners
        if all(self.db.calculate_winner(match_id) for match_id, _, _, _, _, _, _ in winner_bracket_matches):
            # Create the next round for the winner bracket
            next_round = round_number + 1
            is_winner_bracket = True
            new_winner_bracket_match_ids = []

            for i in range(0, len(winner_bracket_matches), 2):
                team_a_name, team_b_name = self.db.get_team_names_for_match(winner_bracket_matches[i][0]), self.db.get_team_names_for_match(winner_bracket_matches[i + 1][0])
                self.db.insert_match(team_a_name, team_b_name, next_round, is_winner_bracket)
                new_winner_bracket_match_ids.append(self.db.conn.lastrowid)

            print(f"Generated Round {next_round} - Winner Bracket: {is_winner_bracket}")
            for i, match_id in enumerate(new_winner_bracket_match_ids):
                team_a_name, team_b_name = self.db.get_team_names_for_match(match_id)
                print(f"Match {match_id}: {team_a_name} vs {team_b_name}")

        # Check if all loser bracket matches have winners
        if all(self.db.calculate_winner(match_id) for match_id, _, _, _, _, _, _ in loser_bracket_matches):
            # Create the next round for the loser bracket
            next_round = round_number + 1
            is_winner_bracket = False
            new_loser_bracket_match_ids = []

            for i in range(0, len(loser_bracket_matches), 2):
                team_a_name, team_b_name = self.db.get_team_names_for_match(loser_bracket_matches[i][0]), self.db.get_team_names_for_match(loser_bracket_matches[i + 1][0])
                self.db.insert_match(team_a_name, team_b_name, next_round, is_winner_bracket)
                new_loser_bracket_match_ids.append(self.db.conn.lastrowid)

            print(f"Generated Round {next_round} - Winner Bracket: {is_winner_bracket}")
            for i, match_id in enumerate(new_loser_bracket_match_ids):
                team_a_name, team_b_name = self.db.get_team_names_for_match(match_id)
                print(f"Match {match_id}: {team_a_name} vs {team_b_name}")

    def update_result(self, match_id, score_a, score_b):
        self.db.update_match_result(match_id, score_a, score_b)
        winner = self.db.calculate_winner(match_id)
        print(f"Match {match_id}: {self.db.get_team_names_for_match(match_id)[0]} vs {self.db.get_team_names_for_match(match_id)[1]} - Score: {score_a} - {score_b} - Winner: {winner}")

    def export_results_to_html(self):
        with open("results.html", "w") as html_file:
            html_file.write("<html><body>")
            html_file.write("<h1>Tournament Results</h1>")
            html_file.write("<table>")
            html_file.write("<tr><th>Match</th><th>Score</th></tr>")
            for match_id, (score_a, score_b) in self.db.get_results().items():
                team_a_name, team_b_name = self.db.get_team_names_for_match(match_id)
                winner = self.db.calculate_winner(match_id)
                html_file.write(f"<tr><td>{team_a_name} vs {team_b_name}</td><td>Score: {score_a} - {score_b} - Winner: {winner or 'Undecided'}</td></tr>")
            html_file.write("</table>")
            html_file.write("</body></html>")

def main():
    db_file = "tournament.db"
    config_file = "config.json"
    tournament = Tournament(db_file, config_file)

    tournament.insert_teams_from_config()
    tournament.generate_matches()

    while True:
        print("Commands:")
        print("1 - List Matches")
        print("2 - Update Result")
        print("3 - Export Results to HTML")
        print("quit - Quit")

        command = input("Enter a command: ")

        if command == "1":
            round_number = int(input("Enter the round number: "))
            is_winner_bracket = input("Is this the winner bracket? (y/n): ").lower() == "y"
            tournament.list_matches(round_number, is_winner_bracket)
        elif command == "2":
            match_id = int(input("Enter the ID of the match for result: "))
            team_a_name, team_b_name = tournament.db.get_team_names_for_match(match_id)
            score_a = int(input(f"Enter score for {team_a_name}: "))
            score_b = int(input(f"Enter score for {team_b_name}: "))
            tournament.update_result(match_id, score_a, score_b)
        elif command == "3":
            tournament.export_results_to_html()
        elif command == "quit":
            break
        else:
            print("Invalid command. Please enter a valid command.")

if __name__ == "__main__":
    main()
