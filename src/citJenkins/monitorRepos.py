'''
Created on Jul 3, 2014

@author: jrl
'''
import os
from urlparse import urlparse
from git import Repo
from github3 import login, GitHubError
from datetime import datetime, timedelta
from ugError import Error


def fail(s):
    raise Error(s)

class MonitoredRepo():
    ''' Connect to a specified git repository and
    provide notification if/when its content is updated.
    '''

    def __init__(self, path):
        (gitrepo,sep, branch) = path.rpartition(':')
        if sep == "":
            gitrepo = branch
            branch = ""
        repo = Repo(os.path.join(gitrepo, ".git"))
        self.localhead = repo.head.commit
        # If a specific branch name is supplied, use it.
        if branch == "":
            # Otherwise, use the current head.
            branch = repo.head.ref.name
        # Save the remote tracking branch so we can filter the appropriate PushEvents
        self.branch = branch
        trackingbranch = repo.heads[branch].tracking_branch()
        if trackingbranch:
            self.trackingbranch = trackingbranch.remote_head
        else:
            fail('no tracking branch for %s:%s' % (gitrepo, self.branch))

        self.connected = False
        self.gh = None
        self.auth = None
        self.repo = repo
        # Can we parse the remote URL?
        self.remoteurl = urlparse(repo.remotes.origin.url)
        if self.remoteurl:
            if self.remoteurl.scheme in ['git','https'] and self.remoteurl.netloc == 'github.com':
                # There should be three components (the first is empty)
                components = self.remoteurl.path.split('/')
                if len(components) == 3:
                    self.remoteowner = components[1]
                    self.remotereponame = components[2]
                else:
                    fail('unexpected path "%s"' % (self.remoteurl.path))
            else:
                fail('unexpected scheme "%s" or location "%s"'
                     % (self.remoteurl.scheme, self.remoteurl.netloc))
        else:
            fail('can\'t parse url "%s"' % (repo.remotes.origin.url))

    def connect(self):
        ''' Connect to the remote repository.'''
        if 'GHRPAT' not in os.environ:
            fail('envrionment variable GHRPAT is not set')
        token = os.environ['GHRPAT']

        # Strip any trailing '.git' off the name of the repo
        reponame = self.remotereponame
        if reponame.endswith('.git'):
            reponame = reponame[:-4]
 
        gh = None
        try:
            gh = login(token=token)
            if gh:
                self.gh = gh
                self.remoterepo = gh.repository(self.remoteowner, reponame)
                self.connected = True
            else:
                fail('can\'t connect/authenticate to remote repo: %s/%s'
                     % (self.remoteowner, reponame))
        except GitHubError as e:
            fail('can\'t connect/authenticate to remote repo: %s/%s: %s'
                % (self.remoteowner, reponame, e.msg))
        return gh

    def getLastPushed(self):
        # Generate a string to facilitate branch reference comparisons
        refMatch = "refs/heads/" + self.trackingbranch

        # Pick up he most recent PushEvent (fortunately, events are ordered
        # in increasing age, i.e., newest first)
        pushevent = None
        for e in self.gh.all_events():
            if e.type == 'PushEvent':
                # Does this refer to our tracking branch?
                if e.payload['ref'] == refMatch:
                    pushevent = e
                    break
        if pushevent is None:
            fail('can\'t find any PushEvents for %s' % (refMatch))
        self.pusheddatetime = pushevent.created_at
        self.pushedhead = pushevent.payload['head']

    def disconnect(self):
        ''' Disconnect from the remote repository.'''
        self.connected = False

    def isChanged(self):
        return 0 if self.pushedhead == self.localhead.hexsha else 1

class MonitorRepos():
    ''' Maintain a connection to github hosted repositories, monitoring them for pushes.'''

    def __init__(self, repoPaths, period = timedelta(minutes = 15)):
        ''' Verify we can contact the remote origins of the specified repositories.'''
        repoMap = {}
        for path in repoPaths:
            try:
                repo = MonitoredRepo(path)
                repoMap[path] = repo
                repo.connect()
                repo.getLastPushed()
            except Error as e:
                print e.msg
        self.repoMap = repoMap
        self.period = period
        self.lastcheck = datetime.now() - period

    def checkRepos(self):
        ''' Return an array of repositories with updated content. '''
        reposToFetch = []
        for name, repo in self.repoMap.iteritems():
            if repo.connected and repo.isChanged():
                reposToFetch.append(name)
        return reposToFetch

    def reposChangedSince(self, period = None):
        reposToFetch = []
        if period is None:
            period = self.period

        # Is it time to check our repo status?
        checkedWhen = datetime.now()
        if checkedWhen > (self.lastcheck + period):
            # See if we have new content
            reposToFetch = self.checkRepos()
            self.lastcheck = checkedWhen
        return reposToFetch

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='indicate if a local clone of a github repo is out of date (needs fetching from origin)')
    parser.add_argument('paths', nargs='+', type=str, help='local filesystem path to a cloned repo to check')
    args = parser.parse_args()
    for path in args.paths:
        try:
            repo = MonitoredRepo(path)
            repo.connect()
            repo.getLastPushed()
            print "Pushed " + repo.pushedhead + " at " + repo.pusheddatetime.ctime() + ('(new)' if repo.isChanged() else '(old)')

        except Error as e:
            print e.msg
