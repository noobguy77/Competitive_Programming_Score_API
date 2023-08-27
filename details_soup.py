import json
import re

# DO NOT import this after requests
import grequests
import requests
import os

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains

from util import get_safe_nested_key


class UsernameError(Exception):
    pass


class PlatformError(Exception):
    pass


class BrokenChangesError(Exception):
    pass


class UserData:
    def __init__(self, username=None):
        self.__username = username

    def update_username(self, username):
        self.__username = username

    def __codechef(self):
        url = "https://www.codechef.com/users/{}".format(self.__username)

        page = requests.get(url)

        soup = BeautifulSoup(page.text, "html.parser")

        try:
            rating = soup.find("div", class_="rating-number").text
        except AttributeError:
            
            raise UsernameError("User not Found")

        stars = soup.find("span", class_="rating")
        if stars:
            stars = stars.text

        def problems_solved_get():
            problem_solved_section = soup.find(
                "section", class_="rating-data-section problems-solved"
            )

            no_solved = problem_solved_section.find_all("h5")

            fully_solved = int(re.findall(r"\d+", no_solved[0].text)[0])


            partially_solved = int(re.findall(r"\d+", no_solved[1].text)[0])

            return fully_solved, partially_solved

        full, partial = problems_solved_get()
        details = {
            "status": "Success",
            "rating": int(rating),
            "stars": stars,
            "fully_solved": full,
            "partially_solved": partial,
        }

        return details

    def __codeforces(self):
        urls = {
            "user_info": {
                "url": f"https://codeforces.com/api/user.info?handles={self.__username}"
            },
            "user_problems": {
                "url": f"https://codeforces.com/api/user.status?handle={self.__username}"
            },
        }
        reqs = [grequests.get(item["url"]) for item in urls.values() if item.get("url")]

        responses = grequests.map(reqs)

        details_api = {}
        problems_api={}
        for page in responses:
            if page.status_code != 200:
                raise UsernameError("User not Found")
            if page.request.url == urls["user_info"]["url"]:
                details_api = page.json()
            if page.request.url == urls["user_problems"]["url"]:
                problems_api = page.json()

        if details_api.get("status") != "OK":
            raise UsernameError("User not Found")

        details_api = details_api["result"][0]

        try:
            rating = details_api["rating"]
            rank = details_api["rank"]
            
        except KeyError:
            rating = "Unrated"
            rank = "Unrated"
        
        if problems_api.get("status") != "OK":
            raise UsernameError("User not Found")
        
        problems_api = problems_api["result"]
        ids=[]
        for submission in problems_api:
            if submission['verdict'] == "OK":
                ids.append(submission['id'])
        problem_count = len(set(ids))
            

        return {
            "status": "Success",
            "username": self.__username,
            "platform": "Codeforces",
            "rating": rating,
            "rank": rank,
            "problem_count" : problem_count
        }

    def __spoj(self):
        url = "https://www.spoj.com/users/{}/".format(self.__username)

        page = requests.get(url)

        soup = BeautifulSoup(page.text, "html.parser")
        details_container = soup.find_all("p")

        points = details_container[2].text.split()[3][1:]
        rank = details_container[2].text.split()[2][1:]

        try:
            points = float(points)

        except ValueError:
            raise UsernameError("User not Found")

        def get_solved_problems():
            table = soup.find("table", class_="table table-condensed")

            rows = table.findChildren("td")

            solved_problems = []
            for row in rows:
                if row.a.text:
                    solved_problems.append(row.a.text)

            return len(solved_problems)

        details = {
            "status": "Success",
            "username": self.__username,
            "platform": "SPOJ",
            "points": float(points),
            "rank": int(rank),
            "solved": get_solved_problems(),
        }

        return details
    
    def __geeksforgeeks(self):
        
        url = "https://auth.geeksforgeeks.org/user/{}".format(self.__username)
        page = requests.get(url)

        if page.status_code != 200:
            raise UsernameError("User not Found")

        soup = BeautifulSoup(page.text, "html.parser")
        score_tag = soup.find_all("div", class_="score_card_left")
        score = int(score_tag[0].find(class_="score_card_value").text)
        problems = int(score_tag[1].find(class_="score_card_value").text)
        details = {
            "status": "Success",
            "username": self.__username,
            "platform": "GeeksForGeeks",
            "score" : score,
            "solved" : problems
        }

        return details
        

    def __interviewbit(self):
        url = "https://www.interviewbit.com/profile/{}".format(self.__username)

        page = requests.get(url)

        if page.status_code != 200:
            raise UsernameError("User not Found")

        soup = BeautifulSoup(page.text, "html.parser")
        details_main = soup.find("div", class_="user-stats")
        details_container = details_main.findChildren("div", recursive=False)

        details = {
            "status": "Success",
            "username": self.__username,
            "platform": "Interviewbit",
            "rank": int(details_container[0].find("div", class_="txt").text),
            "score": int(details_container[1].find("div", class_="txt").text),
        }

        return details
        

    def __leetcode_v2(self):
        def __parse_response(response):

            total_problems_solved = 0
            easy_questions_solved = 0
            medium_questions_solved = 0
            hard_questions_solved = 0

            ac_submissions = get_safe_nested_key(
                ["data", "matchedUser", "submitStats", "acSubmissionNum"], response
            )
            for submission in ac_submissions:
                if submission["difficulty"] == "All":
                    total_problems_solved = submission["count"]
                if submission["difficulty"] == "Easy":
                    easy_questions_solved = submission["count"]
                if submission["difficulty"] == "Medium":
                    medium_questions_solved = submission["count"]
                if submission["difficulty"] == "Hard":
                    hard_questions_solved = submission["count"]

            return {
                "status": "Success",
                "total_problems_solved": str(total_problems_solved),
                "easy_questions_solved": str(easy_questions_solved),
                "medium_questions_solved": str(medium_questions_solved),
                "hard_questions_solved": str(hard_questions_solved),
            }

        url = f"https://leetcode.com/{self.__username}"
        if requests.get(url).status_code != 200:
            raise UsernameError("User not Found")
        payload = {
            "operationName": "getUserProfile",
            "variables": {"username": self.__username},
            "query": "query getUserProfile($username: String!) {  allQuestionsCount {    difficulty    count  }  matchedUser(username: $username) {    contributions {    points      questionCount      testcaseCount    }    profile {    reputation      ranking    }    submitStats {      acSubmissionNum {        difficulty        count        submissions      }      totalSubmissionNum {        difficulty        count        submissions      }    }  }}",
        }
        res = requests.post(
            url="https://leetcode.com/graphql",
            json=payload,
            headers={"referer": f"https://leetcode.com/{self.__username}/"},
        )
        res.raise_for_status()
        res = res.json()
        return __parse_response(res)

    def get_details(self, platform):
        print(platform)
        if platform == "codechef":
            return self.__codechef()

        if platform == "codeforces":
            return self.__codeforces()

        if platform == "spoj":
            try:
                return self.__spoj()
            except AttributeError:
                raise UsernameError("User not Found")

        if platform == "interviewbit":
            return self.__interviewbit()
        
        if platform == "geeksforgeeks":
            return self.__geeksforgeeks()

        if platform == "leetcode":
            return self.__leetcode_v2()

        raise PlatformError("Platform not Found")


if __name__ == "__main__":
    ud = UserData("uwi")
    ans = ud.get_details("leetcode")

    print(ans)

    # leetcode backward compatibility test. Commenting it out as it will fail in future
    # leetcode_ud = UserData('saurabhprakash')
    # leetcode_ans = leetcode_ud.get_details('leetcode')
    # assert leetcode_ans == dict(status='Success', ranking='~100000', total_problems_solved='10',
    #                             acceptance_rate='56.0%', easy_questions_solved='3', total_easy_questions='457',
    #                             medium_questions_solved='5', total_medium_questions='901', hard_questions_solved='2',
    #                             total_hard_questions='365', contribution_points='58', contribution_problems='0',
    #                             contribution_testcases='0', reputation='0')
