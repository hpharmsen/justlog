start_time=$(date +%s)
export VERSION=`python bumpversion.py -v patch`
git commit -v -a -m "publish `date`"
git tag -a $VERSION -m "version $VERSION"
git push origin main
git push origin $VERSION
duration=$(($(date +%s) - start_time))
echo "${GREEN}Published in $duration secs${NC}"
echo ""
echo "run:"
echo "pip install git+https://github.com/hpharmsen/justlog@$VERSION"
