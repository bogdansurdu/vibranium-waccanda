TARGET=$1
shift
arm-linux-gnueabi-gcc -mcpu=arm1176jzf-s "${@}" -o $TARGET -lgcc -fPIC
